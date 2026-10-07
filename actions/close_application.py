"""
Universal application/window closing action for MARK LIV.

Closes the requested foreground application window without requiring the
assistant's Playwright session. For websites such as YouTube, it targets the
browser window whose title contains the site name and sends Ctrl+W, which closes
the tab instead of killing the entire browser.
"""
from __future__ import annotations

import os
import platform
import subprocess
import time

_SYSTEM = platform.system()

_BROWSER_PROCESSES = {
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "edge": "msedge.exe",
    "microsoft edge": "msedge.exe",
    "firefox": "firefox.exe",
    "brave": "brave.exe",
    "opera": "opera.exe",
    "operagx": "opera.exe",
    "opera gx": "opera.exe",
    "vivaldi": "vivaldi.exe",
}

_APP_PROCESSES = {
    "notepad": "notepad.exe",
    "calculator": "calculatorapp.exe",
    "calc": "calculatorapp.exe",
    "spotify": "spotify.exe",
    "discord": "discord.exe",
    "telegram": "telegram.exe",
    "whatsapp": "whatsapp.exe",
    "code": "code.exe",
    "vs code": "code.exe",
    "visual studio code": "code.exe",
}

_SITE_WORDS = {
    "youtube": ["youtube"],
    "gmail": ["gmail"],
    "google maps": ["google maps"],
    "maps": ["google maps", "maps"],
    "facebook": ["facebook"],
    "instagram": ["instagram"],
    "linkedin": ["linkedin"],
    "github": ["github"],
    "netflix": ["netflix"],
}


def _windows():
    try:
        import pygetwindow as gw
        return gw.getAllWindows()
    except Exception:
        return []


def _activate(win) -> bool:
    try:
        if win.isMinimized:
            win.restore()
        win.activate()
        time.sleep(0.15)
        return True
    except Exception:
        return False


def _key_close_tab() -> bool:
    try:
        import pyautogui
        pyautogui.hotkey("ctrl", "w")
        return True
    except Exception:
        return False


def _key_close_window() -> bool:
    try:
        import pyautogui
        pyautogui.hotkey("alt", "f4")
        return True
    except Exception:
        return False


def _find_title(target: str):
    target = target.lower().strip()
    aliases = _SITE_WORDS.get(target, [target])
    for w in _windows():
        title = (getattr(w, "title", "") or "").lower()
        if title and any(a in title for a in aliases):
            return w
    return None


def close_application(parameters=None, player=None, speak=None, **_kwargs) -> str:
    params = parameters or {}
    target = str(params.get("target") or params.get("application") or "").strip().lower()
    if not target:
        return "Please specify what should be closed."

    # First try a matching window. This handles YouTube and individual browser tabs
    # without killing the entire browser process.
    win = _find_title(target)
    if win is not None and _activate(win):
        is_site = target in _SITE_WORDS or any(
            word in (getattr(win, "title", "") or "").lower()
            for values in _SITE_WORDS.values() for word in values
        )
        ok = _key_close_tab() if is_site else _key_close_window()
        if ok:
            return f"Closed {target}."

    # Browser names mean the whole browser when no matching site window exists.
    proc = _BROWSER_PROCESSES.get(target) or _APP_PROCESSES.get(target)
    if proc and _SYSTEM == "Windows":
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", proc],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return f"Closed {target}."
        except Exception as e:
            return f"Could not close {target}: {e}"

    # Last attempt: exact title substring for arbitrary desktop apps.
    win = _find_title(target)
    if win is not None and _activate(win) and _key_close_window():
        return f"Closed {target}."

    return f"I could not find an open window for {target}."


TOOL = {
    "name": "close_application",
    "description": (
        "Closes an open application, browser, website tab, or desktop window. "
        "Use this for commands such as 'close YouTube', 'close Chrome', "
        "'close Calculator', 'close Notepad', or 'close this window'. "
        "For a website, close only its browser tab when possible; do not kill "
        "the entire browser unless the user explicitly asks to close the browser."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "target": {
                "type": "STRING",
                "description": "What to close: website, browser, application, or window title."
            }
        },
        "required": ["target"],
    },
    "handler": close_application,
}
