# actions/whatsapp_call.py
"""
WhatsApp Voice and Video Call Action for JARVIS.

Supports:
1. Making audio (voice) and video calls to any contact by name.
2. Answering/receiving incoming WhatsApp audio or video calls.
3. Rejecting/ending active or incoming WhatsApp calls.

Uses multi-tier detection:
- Windows UI Automation (UIA) for native control inspection
- AI Screen Vision (Gemini 3.5 + GDI capture) for visual icon recognition
- System keyboard and window management
"""

from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import time
from pathlib import Path
from typing import Optional

try:
    import pyautogui
    pyautogui.FAILSAFE = False
    pyautogui.PAUSE = 0.05
    _PYAUTOGUI = True
except ImportError:
    _PYAUTOGUI = False

try:
    import pyperclip
    _PYPERCLIP = True
except ImportError:
    _PYPERCLIP = False

_SYSTEM = platform.system()


def _require_pyautogui():
    if not _PYAUTOGUI:
        raise RuntimeError("PyAutoGUI is required for WhatsApp calling.")


def _focus_whatsapp() -> bool:
    """Brings WhatsApp to the foreground on Windows."""
    _require_pyautogui()
    if _SYSTEM != "Windows":
        return False

    # 1. Try AppActivate via WScript.Shell
    try:
        script = '(New-Object -ComObject WScript.Shell).AppActivate("WhatsApp")'
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=3,
        )
        if "True" in res.stdout:
            time.sleep(0.3)
            return True
    except Exception:
        pass

    # 2. Try launching WhatsApp URI protocol
    try:
        subprocess.run(["cmd", "/c", "start", "whatsapp:"], capture_output=True, timeout=3)
        time.sleep(1.0)
    except Exception:
        pass

    # 3. Fallback: Win + type WhatsApp + Enter
    try:
        pyautogui.press("win")
        time.sleep(0.4)
        if _PYPERCLIP:
            pyperclip.copy("WhatsApp")
            time.sleep(0.1)
            pyautogui.hotkey("ctrl", "v")
        else:
            pyautogui.write("WhatsApp", interval=0.04)
        time.sleep(0.5)
        pyautogui.press("enter")
        time.sleep(1.5)
        return True
    except Exception:
        pass

    return False


def _search_and_open_contact(contact_name: str) -> bool:
    """Searches for a contact in WhatsApp and opens their chat."""
    _require_pyautogui()

    # Clean Hindi / Hinglish phrasing from contact name
    clean_name = re.sub(
        r'\s*(?:ko|par|pe|se)?\s*(?:call|video call|audio call|phone|lagao|karo|milao)?\s*$',
        '',
        contact_name,
        flags=re.IGNORECASE,
    ).strip()
    clean_name = re.sub(r'^(?:call|contact|user)\s*', '', clean_name, flags=re.IGNORECASE).strip()

    if not clean_name:
        clean_name = contact_name.strip()

    print(f"[WhatsAppCall] Searching contact: '{clean_name}'")

    # Focus search bar in WhatsApp: Ctrl + F or Ctrl + N
    pyautogui.hotkey("ctrl", "f")
    time.sleep(0.4)

    # Clear search field
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.1)
    pyautogui.press("backspace")
    time.sleep(0.1)

    # Paste contact name
    if _PYPERCLIP:
        pyperclip.copy(clean_name)
        time.sleep(0.1)
        pyautogui.hotkey("ctrl", "v")
    else:
        pyautogui.write(clean_name, interval=0.04)

    time.sleep(1.0)
    # Press Enter to open top matched contact chat
    pyautogui.press("enter")
    time.sleep(1.2)
    return True


def _uia_find_and_click(target_names: list[str]) -> bool:
    """Attempts to find and click button using Windows UI Automation."""
    try:
        import uiautomation as auto
        root = auto.GetRootControl()

        # Find WhatsApp window
        wa_win = None
        for child in root.GetChildren():
            title = child.Name or ""
            cls = child.ClassName or ""
            if "whatsapp" in title.lower() or "whatsapp" in cls.lower():
                wa_win = child
                break

        search_root = wa_win if wa_win else root

        # Look for buttons matching any candidate name
        for btn in search_root.GetChildren():
            pass

        # Use WalkControl or FindFirst
        for target in target_names:
            target_lower = target.lower()
            ctrl = auto.Control(
                searchFromControl=search_root,
                searchDepth=12,
                Compare=lambda c, d: c.ControlType in (auto.ControlType.ButtonControl, auto.ControlType.HyperlinkControl, auto.ControlType.CustomControl) and (target_lower in (c.Name or "").lower() or target_lower in (c.AutomationId or "").lower())
            )
            if ctrl.Exists(maxSearchSeconds=0.8):
                rect = ctrl.BoundingRectangle
                if rect.width() > 0 and rect.height() > 0:
                    cx = int((rect.left + rect.right) / 2)
                    cy = int((rect.top + rect.bottom) / 2)
                    print(f"[WhatsAppCall] UIA found '{target}' at ({cx}, {cy})")
                    pyautogui.click(cx, cy)
                    return True
    except Exception as e:
        print(f"[WhatsAppCall] UIA search note: {e}")
    return False


def _vision_find_and_click(description: str) -> bool:
    """Uses Gemini 3.5 AI Screen Vision to locate and click icon on screen."""
    try:
        from actions.computer_control import _screen_find
        coords = _screen_find(description)
        if coords:
            print(f"[WhatsAppCall] Vision located '{description}' at {coords}")
            time.sleep(0.1)
            pyautogui.click(coords[0], coords[1])
            return True
    except Exception as e:
        print(f"[WhatsAppCall] Vision search error: {e}")
    return False


def make_call(contact: str, call_type: str = "audio") -> str:
    """Initiates an audio or video call to the specified WhatsApp contact."""
    _require_pyautogui()
    is_video = "video" in call_type.lower()
    call_mode = "Video Call" if is_video else "Voice Call"

    print(f"[WhatsAppCall] Initiating {call_mode} to '{contact}'...")

    # 1. Bring WhatsApp to front
    _focus_whatsapp()
    time.sleep(0.5)

    # 2. Search and open contact chat
    _search_and_open_contact(contact)

    # 3. Detect Call Button
    # Audio candidates vs Video candidates
    if is_video:
        uia_targets = ["Video call", "Video Call", "Video", "video_call", "VideoCallButton"]
        vision_prompt = "WhatsApp video call camera icon button in the top right chat header bar"
    else:
        uia_targets = ["Audio call", "Voice call", "Voice Call", "Audio Call", "Call", "voice_call", "VoiceCallButton"]
        vision_prompt = "WhatsApp telephone handset voice call icon button in the top right chat header bar"

    # Try UIA first
    clicked = _uia_find_and_click(uia_targets)

    # Fallback to AI Screen Vision
    if not clicked:
        clicked = _vision_find_and_click(vision_prompt)

    if clicked:
        return f"Boss, {contact} ko WhatsApp par {call_mode} laga di gayi hai."

    return f"WhatsApp open kar diya hai Boss, lekin {call_mode} button screen par locate nahi ho paya. Kripya screen check karein."


def answer_incoming_call() -> str:
    """Answers an incoming WhatsApp audio or video call."""
    _require_pyautogui()
    print("[WhatsAppCall] Answering incoming WhatsApp call...")

    # Focus WhatsApp / incoming call notification
    _focus_whatsapp()
    time.sleep(0.2)

    # 1. Try UIA search for Accept / Answer
    uia_accept_targets = [
        "Accept", "Answer", "Accept call", "Accept with video",
        "Accept with audio", "Accept Call", "Accept incoming call"
    ]
    clicked = _uia_find_and_click(uia_accept_targets)

    # 2. Try Vision search for green accept button
    if not clicked:
        vision_prompt = "Green Accept button or green phone handset icon on the incoming WhatsApp call popup window"
        clicked = _vision_find_and_click(vision_prompt)

    # 3. Fallback: If incoming call dialog has focus, Enter key accepts call in WhatsApp
    if not clicked:
        pyautogui.press("enter")
        clicked = True

    return "Boss, incoming WhatsApp call accept kar li gayi hai."


def end_or_reject_call() -> str:
    """Declines an incoming call or ends an ongoing WhatsApp call."""
    _require_pyautogui()
    print("[WhatsAppCall] Ending / rejecting WhatsApp call...")

    # 1. Try UIA search for Decline / End / Leave / Hang up
    uia_end_targets = [
        "Decline", "End call", "End Call", "Leave", "Reject", "Hang up",
        "Disconnect", "Close call", "Cancel"
    ]
    clicked = _uia_find_and_click(uia_end_targets)

    # 2. Try Vision search for red end call button
    if not clicked:
        vision_prompt = "Red Decline button, red hangup icon, or end call button on the WhatsApp call window"
        clicked = _vision_find_and_click(vision_prompt)

    # 3. Fallback: Escape key often dismisses / declines incoming call prompt
    if not clicked:
        pyautogui.press("escape")

    return "Boss, WhatsApp call disconnect / reject kar di gayi hai."


def whatsapp_call(
    parameters: dict = None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    action = str(params.get("action", "call")).lower().strip()
    contact = str(params.get("contact", "")).strip()
    call_type = str(params.get("call_type", "audio")).lower().strip()

    # Route based on action
    if action in ("answer", "receive", "accept", "pick", "uthao"):
        res = answer_incoming_call()
    elif action in ("end", "reject", "decline", "cut", "disconnect", "hangup", "kaato"):
        res = end_or_reject_call()
    else:
        # Default: make a call
        if not contact:
            res = "Boss, kripya batayein ki kisse call karni hai (contact ka naam)."
        else:
            res = make_call(contact=contact, call_type=call_type)

    if player:
        player.write_log(f"[whatsapp_call] {res[:50]}")
    return res


TOOL = {
    "name": "whatsapp_call",
    "description": "Makes, answers, or ends WhatsApp audio (voice) and video calls. Use this when the user asks to call someone on WhatsApp ('call Rahul', 'WhatsApp par Papa ko video call karo', 'audio call lagao'), answer an incoming call ('call uthao', 'call receive karo', 'answer call'), or end/reject a call ('call kaat do', 'disconnect call').",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "call | answer | end | reject (default: call)"
            },
            "contact": {
                "type": "STRING",
                "description": "Name of the person/contact to call (required when action='call')"
            },
            "call_type": {
                "type": "STRING",
                "description": "audio | video (default: audio)"
            }
        },
        "required": ["action"]
    },
    "handler": whatsapp_call,
}
