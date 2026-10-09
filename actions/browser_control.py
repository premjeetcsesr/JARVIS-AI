
from __future__ import annotations

import asyncio
import concurrent.futures
import json
import os
import re
import platform
import shutil
import subprocess
import threading
import time
import webbrowser
from pathlib import Path
from typing import Optional

from playwright.async_api import (
    async_playwright,
    BrowserContext,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeout,
)
_OS = platform.system()   # "Windows" | "Darwin" | "Linux"

def _normalize_url(url: str) -> str:
    """
    Bare words like "instagram" → "https://instagram.com"
    Domains like "instagram.com" → "https://instagram.com"
    Full URLs pass through unchanged.
    """
    url = url.strip()
    if not url:
        return "about:blank"
    if "://" in url:
        return url
    # No dot at all → assume .com  (e.g. "instagram" → "instagram.com")
    if "." not in url:
        url = url + ".com"
    return "https://" + url


def _user_agent() -> str:
    if _OS == "Windows":
        return (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    if _OS == "Darwin":
        return (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    return (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )


def _real_profile_dir(browser: str) -> str:
    home  = Path.home()
    local = os.environ.get("LOCALAPPDATA", "")
    roam  = os.environ.get("APPDATA", "")

    candidates: list[Path] = []

    if _OS == "Windows":
        m = {
            "chrome":   [Path(local) / "Google"          / "Chrome"          / "User Data"],
            "edge":     [Path(local) / "Microsoft"        / "Edge"            / "User Data"],
            "brave":    [Path(local) / "BraveSoftware"    / "Brave-Browser"   / "User Data"],
            "vivaldi":  [Path(local) / "Vivaldi"          / "User Data"],
            "opera":    [Path(roam)  / "Opera Software"   / "Opera Stable",
                         Path(local) / "Opera Software"   / "Opera Stable"],
            "operagx":  [Path(roam)  / "Opera Software"   / "Opera GX Stable",
                         Path(local) / "Opera Software"   / "Opera GX Stable"],
        }
        candidates = m.get(browser, [])

    elif _OS == "Darwin":
        lib = home / "Library" / "Application Support"
        m = {
            "chrome":   [lib / "Google"             / "Chrome"],
            "edge":     [lib / "Microsoft Edge"],
            "brave":    [lib / "BraveSoftware"       / "Brave-Browser"],
            "vivaldi":  [lib / "Vivaldi"],
            "opera":    [lib / "com.operasoftware.Opera"],
            "operagx":  [lib / "com.operasoftware.OperaGX"],
        }
        candidates = m.get(browser, [])

    elif _OS == "Linux":
        cfg = home / ".config"
        m = {
            "chrome":   [cfg / "google-chrome", cfg / "chromium"],
            "edge":     [cfg / "microsoft-edge"],
            "brave":    [cfg / "BraveSoftware" / "Brave-Browser"],
            "vivaldi":  [cfg / "vivaldi"],
            "opera":    [cfg / "opera"],
            "operagx":  [cfg / "opera-gx"],
        }
        candidates = m.get(browser, [])

    for p in candidates:
        if p.exists():
            print(f"[Browser] [+] Real profile found for {browser}: {p}")
            return str(p)

    fallback = home / ".jarvis_profiles" / browser
    fallback.mkdir(parents=True, exist_ok=True)
    print(f"[Browser] [!]  Real profile not found for {browser}, using: {fallback}")
    return str(fallback)

def _firefox_profile_dir() -> Optional[str]:
    home = Path.home()

    if _OS == "Windows":
        base = Path(os.environ.get("APPDATA", "")) / "Mozilla" / "Firefox"
    elif _OS == "Darwin":
        base = home / "Library" / "Application Support" / "Firefox"
    else:
        base = home / ".mozilla" / "firefox"

    ini = base / "profiles.ini"
    if not ini.exists():
        return None

    current: dict[str, str] = {}
    default_path: Optional[str] = None

    for line in ini.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line.startswith("["):
            p = current.get("Path", "")
            if p and current.get("Default") == "1":
                is_rel = current.get("IsRelative", "1") == "1"
                default_path = str(base / p) if is_rel else p
            current = {}
        elif "=" in line:
            k, _, v = line.partition("=")
            current[k.strip()] = v.strip()

    p = current.get("Path", "")
    if p and current.get("Default") == "1":
        is_rel = current.get("IsRelative", "1") == "1"
        default_path = str(base / p) if is_rel else p

    if default_path and Path(default_path).exists():
        print(f"[Browser] Firefox real profile: {default_path}")
        return default_path
    return None

def _find_opera_windows() -> Optional[str]:
    local  = os.environ.get("LOCALAPPDATA", "")
    prog   = os.environ.get("PROGRAMFILES", "")
    prog86 = os.environ.get("PROGRAMFILES(X86)", "")

    candidates = [
        Path(local)  / "Programs" / "Opera"    / "opera.exe",
        Path(local)  / "Programs" / "Opera GX" / "opera.exe",
        Path(prog)   / "Opera"    / "opera.exe",
        Path(prog86) / "Opera"    / "opera.exe",
    ]
    for p in candidates:
        if p.exists():
            print(f"[Browser] Opera found at: {p}")
            return str(p)

    try:
        import winreg
        keys = [
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\opera.exe",
            r"SOFTWARE\Clients\StartMenuInternet\OperaStable\shell\open\command",
            r"SOFTWARE\Clients\StartMenuInternet\OperaGXStable\shell\open\command",
            r"SOFTWARE\Clients\StartMenuInternet\opera\shell\open\command",
        ]
        for key_path in keys:
            for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                try:
                    k   = winreg.OpenKey(hive, key_path)
                    val = winreg.QueryValue(k, None)
                    winreg.CloseKey(k)
                    exe = val.strip().strip('"').split('"')[0].split(" --")[0].strip()
                    if exe and Path(exe).exists():
                        print(f"[Browser] Opera found via registry: {exe}")
                        return exe
                except Exception:
                    continue
    except Exception:
        pass

    return shutil.which("opera") or None

def _find_exe_windows(prog_name: str) -> Optional[str]:
    try:
        import winreg
        paths_to_try = [
            rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{prog_name}.exe",
            rf"SOFTWARE\Clients\StartMenuInternet\{prog_name}\shell\open\command",
        ]
        for key_path in paths_to_try:
            for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                try:
                    k   = winreg.OpenKey(hive, key_path)
                    val = winreg.QueryValue(k, None)
                    winreg.CloseKey(k)
                    exe = val.strip().strip('"').split('"')[0].split(" --")[0].strip()
                    if exe and Path(exe).exists():
                        return exe
                except Exception:
                    continue
    except Exception:
        pass
    return None

_BROWSER_SPECS: dict[str, dict] = {
    "Windows": {
        "chrome":   {"engine": "chromium", "channel": "chrome",  "bins": []},
        "edge":     {"engine": "chromium", "channel": "msedge",  "bins": []},
        "firefox":  {"engine": "firefox",  "channel": None,      "bins": ["firefox.exe"]},
        "opera":    {"engine": "chromium", "channel": None,      "bins": ["opera.exe"],  "special": "opera_windows"},
        "operagx":  {"engine": "chromium", "channel": None,      "bins": [],             "special": "opera_windows"},
        "brave":    {"engine": "chromium", "channel": None,      "bins": ["brave.exe"]},
        "vivaldi":  {"engine": "chromium", "channel": None,      "bins": ["vivaldi.exe"]},
        "safari":   None,
    },
    "Darwin": {
        "chrome":   {"engine": "chromium", "channel": "chrome",  "bins": []},
        "edge":     {"engine": "chromium", "channel": "msedge",  "bins": ["microsoft-edge"]},
        "firefox":  {"engine": "firefox",  "channel": None,      "bins": ["firefox"]},
        "opera":    {"engine": "chromium", "channel": None,      "bins": ["opera"]},
        "operagx":  {"engine": "chromium", "channel": None,      "bins": ["opera"]},
        "brave":    {"engine": "chromium", "channel": None,      "bins": ["brave browser", "brave"]},
        "vivaldi":  {"engine": "chromium", "channel": None,      "bins": ["vivaldi"]},
        "safari":   {"engine": "webkit",   "channel": None,      "bins": []},
    },
    "Linux": {
        "chrome":   {"engine": "chromium", "channel": None,
                     "bins": ["google-chrome", "google-chrome-stable", "chromium-browser", "chromium"]},
        "edge":     {"engine": "chromium", "channel": None,
                     "bins": ["microsoft-edge", "microsoft-edge-stable"]},
        "firefox":  {"engine": "firefox",  "channel": None, "bins": ["firefox"]},
        "opera":    {"engine": "chromium", "channel": None, "bins": ["opera", "opera-stable"]},
        "operagx":  {"engine": "chromium", "channel": None, "bins": ["opera", "opera-stable"]},
        "brave":    {"engine": "chromium", "channel": None, "bins": ["brave-browser", "brave"]},
        "vivaldi":  {"engine": "chromium", "channel": None, "bins": ["vivaldi-stable", "vivaldi"]},
        "safari":   None,
    },
}

_ALIASES: dict[str, str] = {
    "google chrome":   "chrome",
    "google-chrome":   "chrome",
    "microsoft edge":  "edge",
    "ms edge":         "edge",
    "msedge":          "edge",
    "mozilla firefox": "firefox",
    "opera gx":        "operagx",
    "opera_gx":        "operagx",
}


def _resolve_browser(name: str) -> dict | None:
    name   = _ALIASES.get(name.lower().strip(), name.lower().strip())
    os_map = _BROWSER_SPECS.get(_OS, {})
    spec   = os_map.get(name)
    if spec is None:
        return None

    engine  = spec["engine"]
    channel = spec.get("channel")
    bins    = spec.get("bins", [])
    exe     = None

    if spec.get("special") == "opera_windows":
        exe = _find_opera_windows()
        if not exe:
            print(f"[Browser] [!]  Opera executable not found on Windows.")
        return {"engine": engine, "exe": exe, "channel": channel}

    for b in bins:
        found = shutil.which(b)
        if found:
            exe = found
            break

    if not exe and _OS == "Darwin":
        app_names = {
            "chrome":  ["Google Chrome.app"],
            "edge":    ["Microsoft Edge.app"],
            "firefox": ["Firefox.app"],
            "opera":   ["Opera.app", "Opera GX.app"],
            "brave":   ["Brave Browser.app"],
            "vivaldi": ["Vivaldi.app"],
        }
        for app in app_names.get(name, []):
            app_dir = Path("/Applications") / app / "Contents" / "MacOS"
            if app_dir.exists():
                found_bins = list(app_dir.iterdir())
                if found_bins:
                    exe = str(found_bins[0])
                    break

    if not exe and _OS == "Windows" and not channel:
        exe = _find_exe_windows(name)

    return {"engine": engine, "exe": exe, "channel": channel}


def _detect_default_browser() -> str:
    # 1. Prioritize browser currently running with an open window on the desktop
    try:
        if _OS == "Windows":
            for b, proc in (("chrome", "chrome.exe"), ("edge", "msedge.exe"), ("brave", "brave.exe"), ("opera", "opera.exe"), ("firefox", "firefox.exe")):
                res = subprocess.run(["tasklist", "/fi", f"imagename eq {proc}"], capture_output=True, text=True, timeout=2)
                if proc.lower() in res.stdout.lower():
                    return b
    except Exception:
        pass

    try:
        if _OS == "Windows":
            import winreg
            k = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\Shell\Associations"
                r"\UrlAssociations\http\UserChoice",
            )
            prog_id = winreg.QueryValueEx(k, "ProgId")[0].lower()
            winreg.CloseKey(k)
            for kw in ("chrome", "edge", "brave", "opera", "vivaldi", "firefox"):
                if kw in prog_id:
                    return kw
        elif _OS == "Darwin":
            out = subprocess.run(
                ["defaults", "read",
                 "com.apple.LaunchServices/com.apple.launchservices.secure",
                 "LSHandlers"],
                capture_output=True, text=True, timeout=5,
            ).stdout.lower()
            for kw in ("chrome", "edge", "brave", "opera", "vivaldi", "safari", "firefox"):
                if kw in out:
                    return kw
        elif _OS == "Linux":
            out = subprocess.run(
                ["xdg-settings", "get", "default-web-browser"],
                capture_output=True, text=True, timeout=5,
            ).stdout.lower()
            for kw in ("chrome", "edge", "brave", "opera", "vivaldi", "firefox"):
                if kw in out:
                    return kw
    except Exception:
        pass
    return "chrome"


_SEARCH_ENGINES: dict[str, str] = {
    "google":     "https://www.google.com/search?q=",
    "bing":       "https://www.bing.com/search?q=",
    "duckduckgo": "https://duckduckgo.com/?q=",
    "yandex":     "https://yandex.com/search/?text=",
}

_MAC_APP_NAMES: dict[str, str] = {
    "chrome":  "Google Chrome",
    "edge":    "Microsoft Edge",
    "firefox": "Firefox",
    "opera":   "Opera",
    "operagx": "Opera GX",
    "brave":   "Brave Browser",
    "vivaldi": "Vivaldi",
    "safari":  "Safari",
}

# Windows registry lookup names for browsers whose spec has no explicit binary
_WIN_EXE_HINTS: dict[str, str] = {"chrome": "chrome", "edge": "msedge"}


def _open_native(url: str, browser_name: Optional[str]) -> str:
    """
    Opens the user's REAL browser normally -- with their own profile,
    logged-in accounts and extensions. No automation attaches, so an
    about:blank tab or a blank profile NEVER shows up.
    If url is empty the browser starts with no URL (its own start page /
    session restore) -- exactly as if the user had opened it themselves.
    Works on all three of Windows / macOS / Linux.
    """
    url = _normalize_url(url) if url and url.strip() else ""
    if url == "about:blank":
        url = ""

    name = None
    if browser_name:
        name = _ALIASES.get(browser_name.lower().strip(), browser_name.lower().strip())
    elif not url:
        # No URL → only a window will open; needs the default browser's exe
        name = _detect_default_browser()

    # Specific browser → launch its own executable, exactly like the user would.
    if name:
        if _OS == "Darwin":
            app = _MAC_APP_NAMES.get(name)
            if app:
                cmd = ["open", "-a", app] + ([url] if url else [])
                try:
                    subprocess.run(cmd, check=True, timeout=10)
                    return f"Opened in {name}: {url}" if url else f"Opened {name}."
                except Exception as e:
                    print(f"[Browser] 'open -a {app}' failed ({e}), trying binary...")

        spec = _resolve_browser(name)
        exe  = spec.get("exe") if spec else None
        if not exe and _OS == "Windows":
            if name in ("opera", "operagx"):
                exe = _find_opera_windows()
            else:
                exe = _find_exe_windows(_WIN_EXE_HINTS.get(name, name))
        if exe:
            try:
                subprocess.Popen(
                    [exe, url] if url else [exe],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                return f"Opened in {name}: {url}" if url else f"Opened {name}."
            except Exception as e:
                print(f"[Browser] Native launch failed for {name}: {e}")
        print(f"[Browser] '{name}' not found -- falling back to default browser.")

    if not url:
        return "Could not find a browser to open."

    # Default browser via the OS -- exactly like the user clicking a link.
    try:
        if _OS == "Windows":
            os.startfile(url)                       # ShellExecute → default browser
        elif _OS == "Darwin":
            subprocess.run(["open", url], check=True, timeout=10)
        else:
            subprocess.Popen(
                ["xdg-open", url],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        return f"Opened in your default browser: {url}"
    except Exception:
        try:
            if webbrowser.open(url):
                return f"Opened in your default browser: {url}"
        except Exception:
            pass
        return f"Could not open a browser for: {url}"


class _BrowserSession:
    """
    A full session for one browser instance.
    All browsers open on the real profile via launch_persistent_context.
    """

    def __init__(self, browser_name: str):
        self.browser_name = browser_name
        self._spec        = _resolve_browser(browser_name)

        self._loop:    asyncio.AbstractEventLoop | None = None
        self._thread:  threading.Thread | None          = None
        self._ready    = threading.Event()

        self._pw:      Playwright     | None = None
        self._context: BrowserContext | None = None
        self._page:    Page           | None = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name=f"BrowserThread-{self.browser_name}",
        )
        self._thread.start()
        self._ready.wait(timeout=20)

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._async_init())
        self._ready.set()
        self._loop.run_forever()

    async def _async_init(self):
        self._pw = await async_playwright().start()

    def run(self, coro, timeout: int = 60) -> str:
        if not self._loop:
            raise RuntimeError(f"Session for '{self.browser_name}' not started.")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    def close(self):
        if self._loop:
            asyncio.run_coroutine_threadsafe(self._async_close(), self._loop).result(10)

    async def _async_close(self):
        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass
        if self._pw:
            try:
                await self._pw.stop()
            except Exception:
                pass
        self._context = self._page = None

    async def _adopt_page(self) -> Page:
        """
        launch_persistent_context already opens a starting tab.
        Instead of opening a new blank tab (about:blank), it adopts that tab --
        so the user never sees an extra blank tab.
        Skips Chrome profile picker pages (chrome://profile-picker, etc.).
        """
        await asyncio.sleep(0.5)
        pages = self._context.pages
        # Skip Chrome internal pages like profile picker
        _SKIP_URLS = ("chrome://profile-picker", "chrome://welcome",
                      "edge://profile-picker", "about:blank#profile")
        for page in pages:
            url = page.url or ""
            if not any(url.startswith(skip) for skip in _SKIP_URLS):
                return page
        # All pages are chrome-internal -- open a real usable page
        return await self._context.new_page()

    async def _dismiss_profile_picker(self) -> None:
        """If Chrome opened a profile picker, try to click the first available profile."""
        try:
            pages = self._context.pages
            for page in pages:
                url = page.url or ""
                if "profile-picker" in url or "profile-picker" in (await page.title()).lower():
                    print("[Browser] Profile picker detected, dismissing...")
                    # Try clicking the first user profile tile
                    for sel in (
                        "[data-testid='profile-picker-item']:first-child",
                        ".profile-card",
                        "button.profile-picker-button",
                        "button:visible",
                    ):
                        try:
                            loc = page.locator(sel)
                            if await loc.count() > 0:
                                await loc.first.click(timeout=3_000)
                                await asyncio.sleep(1.0)
                                print("[Browser] Profile picker dismissed.")
                                # Re-adopt a usable page
                                self._page = await self._adopt_page()
                                return
                        except Exception:
                            pass
        except Exception as e:
            print(f"[Browser] Profile picker dismissal failed: {e}")

    async def _launch(self):
        """
        Launches the browser with the real user profile.
        Does nothing if the context is already open.
        """
        if self._context is not None:
            return

        if self._spec is None:
            raise RuntimeError(
                f"'{self.browser_name}' bu platformda ({_OS}) desteklenmiyor."
            )

        engine_name = self._spec["engine"]
        exe         = self._spec["exe"]
        channel     = self._spec["channel"]
        engine_obj  = getattr(self._pw, engine_name)

        # Check if Chrome / Chromium is already running with remote debugging (CDP)
        if engine_name == "chromium":
            try:
                cdp_browser = await self._pw.chromium.connect_over_cdp("http://localhost:9222", timeout=1500)
                if cdp_browser.contexts:
                    self._context = cdp_browser.contexts[0]
                    self._page = await self._adopt_page()
                    print(f"[Browser] [+] Connected to active Chrome via CDP (localhost:9222)")
                    return
            except Exception:
                pass

        if engine_name == "firefox":
            profile = _firefox_profile_dir() or str(
                Path.home() / ".jarvis_profiles" / "firefox"
            )
            kwargs: dict = {
                "headless":    False,
                "slow_mo":     0,
                "viewport":    None,
                "no_viewport": True,
                "timeout":     25_000,
            }
            if exe:
                kwargs["executable_path"] = exe
            try:
                self._context = await engine_obj.launch_persistent_context(profile, **kwargs)
            except Exception as e:
                print(f"[Browser] Firefox real profile failed ({e}), using JARVIS profile")
                jarvis = str(Path.home() / ".jarvis_profiles" / "firefox_jarvis")
                Path(jarvis).mkdir(parents=True, exist_ok=True)
                self._context = await engine_obj.launch_persistent_context(jarvis, **kwargs)

            self._page = await self._adopt_page()
            print(f"[Browser] [+] Firefox launched")
            return

        if engine_name == "webkit":
            safari_profile = str(Path.home() / ".jarvis_profiles" / "safari")
            Path(safari_profile).mkdir(parents=True, exist_ok=True)
            kwargs = {
                "headless":    False,
                "slow_mo":     0,
                "viewport":    None,
                "no_viewport": True,
                "timeout":     25_000,
            }
            self._context = await engine_obj.launch_persistent_context(safari_profile, **kwargs)
            self._page = await self._adopt_page()
            print(f"[Browser] [+] Safari launched")
            return

        profile = _real_profile_dir(self.browser_name)

        kwargs = {
            "headless":    False,
            "slow_mo":     0,
            "viewport":    None,
            "no_viewport": True,
            "timeout":     25_000,
            "args": [
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--disable-default-apps",
                "--no-default-browser-check",
                "--disable-profile-picker",           # suppress "Who's using Chrome?" picker
                "--disable-features=IdentityConsistencyConsentBump",  # disable profile sync dialog
                "--profile-management-disabled",      # disable profile management bubble
                "--suppress-message-center-popups",   # suppress overlay popups
                "--noerrdialogs",                     # suppress error dialogs
            ],
        }

        if exe:
            kwargs["executable_path"] = exe
        elif channel:
            kwargs["channel"] = channel

        label = (
            f"{self.browser_name}"
            + (f"/{channel}" if channel else "")
            + (f" @ {exe}" if exe else "")
        )

        try:
            self._context = await engine_obj.launch_persistent_context(profile, **kwargs)
            self._page = await self._adopt_page()
            print(f"[Browser] [+] Launched [{label}] profile={profile}")
            return
        except Exception as e:
            print(f"[Browser] [!]  Real profile failed for {label}: {e}")

        # The real profile could not be opened (browser already open / locked
        # profile / newer Chrome versions block the real profile under
        # automation). Fall back to a persistent JARVIS automation profile --
        # accounts logged in here once stay logged in on later sessions too.
        jarvis_profile = str(Path.home() / ".jarvis_profiles" / self.browser_name)
        Path(jarvis_profile).mkdir(parents=True, exist_ok=True)
        print(f"[Browser] Retrying with JARVIS profile: {jarvis_profile}")

        try:
            self._context = await engine_obj.launch_persistent_context(jarvis_profile, **kwargs)
            self._page = await self._adopt_page()
            print(f"[Browser] [+] Launched [{label}] with JARVIS profile "
                  f"(sign-ins persist across sessions)")
        except Exception as e2:
            raise RuntimeError(f"Could not launch {self.browser_name}: {e2}") from e2


    async def _get_page(self) -> Page:
        await self._launch()
        # Auto-dismiss Chrome profile picker if it appeared on launch
        await self._dismiss_profile_picker()
        # If somehow page got closed, open a fresh one
        if self._page is None or self._page.is_closed():
            self._page = await self._context.new_page()
            await asyncio.sleep(0.2)
        # If our adopted page is still a chrome-internal page, swap to a real page
        if self._page:
            url = self._page.url or ""
            if url.startswith(("chrome://", "edge://", "about:newtab")):
                usable = await self._adopt_page()
                if usable is not self._page:
                    self._page = usable
        return self._page

    async def go_to(self, url: str) -> str:

        url      = _normalize_url(url)
        page     = await self._get_page()
        prev_url = page.url

        async def _do_goto(p: Page) -> str:
            """Attempt navigation and return the resulting URL (may still be blank)."""
            try:
                await p.goto(url, wait_until="domcontentloaded", timeout=30_000)
                await asyncio.sleep(0.3)
            except PlaywrightTimeout:
                pass   # page may have partially loaded -- check URL below
            except Exception as e:
                print(f"[Browser] goto exception (non-fatal): {e}")
            return p.url

        result_url = await _do_goto(page)

        if result_url in ("about:blank", "", None, prev_url) and prev_url in ("about:blank", "", None):
            print(f"[Browser] Still blank after goto -- retrying on new tab: {url}")
            try:
                new_page   = await self._context.new_page()
                self._page = new_page
                result_url = await _do_goto(new_page)
            except Exception as e:
                print(f"[Browser] New-tab retry failed: {e}")

        if result_url and result_url not in ("about:blank", "", None):
            return f"Opened: {result_url}"
        return f"Could not open: {url}"

    async def search(self, query: str, engine: str = "google") -> str:
        base = _SEARCH_ENGINES.get(engine.lower(), _SEARCH_ENGINES["google"])
        return await self.go_to(base + query.replace(" ", "+"))

    async def click(self, selector: str = None, text: str = None, description: str = None) -> str:
        page = await self._get_page()
        target = description or text
        try:
            if selector:
                try:
                    await page.click(selector, timeout=6_000)
                    return f"Clicked selector: {selector}"
                except Exception:
                    pass
            if target:
                res = await self.smart_click(target)
                if not any(k in res.lower() for k in ("could not find", "not found", "error")):
                    return res
            if text:
                try:
                    await page.get_by_text(text, exact=False).first.click(timeout=6_000)
                    return f"Clicked text: '{text}'"
                except Exception:
                    pass
            return f"Could not find element: '{target or selector}'"
        except PlaywrightTimeout:
            return "Element not found (timeout)."
        except Exception as e:
            return f"Click error: {e}"

    async def type_text(self, selector: str = None, text: str = "",
                        clear_first: bool = True, description: str = None,
                        press_enter: bool = False) -> str:
        page = await self._get_page()
        try:
            if description:
                res = await self.smart_type(description, text)
                if not any(k in res.lower() for k in ("could not find", "not found", "error")):
                    if press_enter:
                        await asyncio.sleep(0.1)
                        await page.keyboard.press("Enter")
                    return res
            el = page.locator(selector).first if selector else page.locator(":focus")
            if clear_first:
                try:
                    await el.clear()
                except Exception:
                    pass
            await el.type(text, delay=35)
            if press_enter:
                await asyncio.sleep(0.1)
                await page.keyboard.press("Enter")
            return f"Typed: '{text}'"
        except Exception as e:
            return f"Type error: {e}"

    async def scroll(self, direction: str = "down", amount: int = 500) -> str:
        page = await self._get_page()
        try:
            y = amount if direction == "down" else -amount
            await page.mouse.wheel(0, y)
            return f"Scrolled {direction}."
        except Exception as e:
            return f"Scroll error: {e}"

    async def press(self, key: str) -> str:
        page = await self._get_page()
        try:
            await page.keyboard.press(key)
            return f"Pressed: {key}"
        except Exception as e:
            return f"Key error: {e}"

    async def get_text(self) -> str:
        page = await self._get_page()
        try:
            text = await page.inner_text("body")
            return text[:4_000]
        except Exception as e:
            return f"Could not get page text: {e}"

    async def get_url(self) -> str:
        page = await self._get_page()
        return page.url

    async def fill_form(self, fields: dict) -> str:
        page    = await self._get_page()
        results = []
        for selector, value in fields.items():
            try:
                el = page.locator(selector).first
                await el.clear()
                await el.type(str(value), delay=40)
                results.append(f"✓ {selector}")
            except Exception as e:
                results.append(f"✗ {selector}: {e}")
        return "Form filled: " + ", ".join(results)

    async def get_all_clickable_elements(self) -> list[dict]:
        """Scans and returns all visible interactive elements (buttons, links, inputs)."""
        page = await self._get_page()
        js_code = """
        () => {
            const selectors = 'button, a, input[type="button"], input[type="submit"], [role="button"], [role="link"], [role="tab"], [role="menuitem"], div[role="button"], span[role="button"], [onclick]';
            const nodes = Array.from(document.querySelectorAll(selectors));
            const results = [];
            for (let el of nodes) {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                if (rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none' && style.opacity !== '0') {
                    const text = (el.innerText || el.value || el.getAttribute('aria-label') || el.getAttribute('title') || el.getAttribute('placeholder') || el.id || '').trim();
                    if (text && text.length < 100) {
                        results.push({
                            tag: el.tagName.toLowerCase(),
                            text: text.replace(/\\s+/g, ' '),
                            role: el.getAttribute('role') || el.tagName.toLowerCase()
                        });
                    }
                }
            }
            return results;
        }
        """
        try:
            return await page.evaluate(js_code)
        except Exception:
            return []

    async def smart_click(self, description: str) -> str:
        page = await self._get_page()
        raw_desc = (description or "").strip()
        desc_lower = raw_desc.lower()

        # Clean Hindi/Hinglish phrasing
        clean_desc = re.sub(
            r'\s*(?:par|pe|ko|bhi|sa)?\s*(?:click|press|karo|kar do|dabao|daba do|chalao|khol do|trigger|trigger karo)\s*$', 
            '', 
            desc_lower, 
            flags=re.IGNORECASE
        ).strip()
        clean_desc = re.sub(r'^(?:browser|brouser|chrome)\s*(?:me|in|par)?\s*', '', clean_desc).strip()

        generic_keywords = {
            "kisi button", "any button", "koi button", "button", "koi bhi button",
            "koi sa button", "a button", "some button", "kisi bhi button", "trigger",
            "first button", "pehla button", "primary button", ""
        }
        if clean_desc in generic_keywords:
            # Generic click: click first visible button or interactive action element
            for sel in (
                "button:visible",
                "[role='button']:visible",
                "input[type='submit']:visible",
                "input[type='button']:visible",
                "a.btn:visible",
                "a[role='button']:visible",
            ):
                try:
                    loc = page.locator(sel)
                    if await loc.count() > 0:
                        await loc.first.click(timeout=4_000)
                        return "Clicked visible button on page."
                except Exception:
                    pass

        # Also strip role words from name ("subscribe button" -> "subscribe")
        core_name = re.sub(r'\s*(?:button|btn|link|icon|tab)\s*$', '', clean_desc, flags=re.IGNORECASE).strip()
        names_to_try = [raw_desc]
        if clean_desc and clean_desc != raw_desc:
            names_to_try.append(clean_desc)
        if core_name and core_name not in names_to_try:
            names_to_try.append(core_name)

        for name_candidate in names_to_try:
            if not name_candidate:
                continue
            for role in ("button", "link", "searchbox", "textbox", "menuitem", "tab"):
                try:
                    loc = page.get_by_role(role, name=re.compile(re.escape(name_candidate), re.I))
                    if await loc.count() > 0:
                        await loc.first.click(timeout=4_000)
                        return f"Clicked ({role}): '{name_candidate}'"
                except Exception:
                    pass

            for attempt in (
                lambda n=name_candidate: page.get_by_text(n, exact=False).first.click(timeout=4_000),
                lambda n=name_candidate: page.get_by_placeholder(n, exact=False).first.click(timeout=4_000),
                lambda n=name_candidate: page.locator(
                    f'[alt*="{n}" i],[title*="{n}" i],'
                    f'[aria-label*="{n}" i]'
                ).first.click(timeout=4_000),
            ):
                try:
                    await attempt()
                    return f"Clicked: '{name_candidate}'"
                except Exception:
                    pass

        # JavaScript DOM evaluate fallback for modern web apps & nested elements
        try:
            target_json = json.dumps(clean_desc or core_name or raw_desc)
            js_click = f"""
            () => {{
                const target = {target_json}.toLowerCase();
                const selectors = 'button, a, input[type="button"], input[type="submit"], [role="button"], [role="link"], [role="tab"], [role="menuitem"], div[role="button"], span[role="button"], [onclick], button *, a *';
                const candidates = Array.from(document.querySelectorAll(selectors));
                
                // 1. Exact match
                for (let el of candidates) {{
                    const clickable = el.closest('button, a, [role="button"], input, [onclick]') || el;
                    const text = (clickable.innerText || clickable.value || clickable.getAttribute('aria-label') || clickable.getAttribute('title') || '').trim().toLowerCase();
                    if (text === target) {{
                        clickable.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                        clickable.click();
                        return "exact";
                    }}
                }}
                // 2. Substring match
                for (let el of candidates) {{
                    const clickable = el.closest('button, a, [role="button"], input, [onclick]') || el;
                    const text = (clickable.innerText || clickable.value || clickable.getAttribute('aria-label') || clickable.getAttribute('title') || '').trim().toLowerCase();
                    if (text && text.includes(target)) {{
                        clickable.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                        clickable.click();
                        return "contains";
                    }}
                }}
                return null;
            }}
            """
            js_res = await page.evaluate(js_click)
            if js_res:
                return f"Clicked element via DOM: '{clean_desc or raw_desc}'"
        except Exception:
            pass

        return f"Could not find element: '{description}'"

    async def smart_type(self, description: str, text: str) -> str:
        page = await self._get_page()
        candidates = [
            ("placeholder", page.get_by_placeholder(description, exact=False)),
            ("label",       page.get_by_label(description, exact=False)),
            ("role",        page.get_by_role("textbox", name=description)),
            ("searchbox",   page.get_by_role("searchbox")),
            ("combobox",    page.get_by_role("combobox", name=description)),
        ]
        for method, loc in candidates:
            try:
                el = loc.first
                if await el.count() == 0:
                    continue
                await el.clear()
                await el.type(text, delay=50)
                return f"Typed into ({method}): '{description}'"
            except Exception:
                continue
        return f"Could not find input: '{description}'"

    async def new_tab(self, url: str = "") -> str:
        page = await self._get_page()
        ctx  = page.context
        new  = await ctx.new_page()
        self._page = new
        if url:
            return await self.go_to(url)
        return "New tab opened."

    async def close_tab(self) -> str:
        page = self._page
        if page and not page.is_closed():
            ctx   = page.context
            await page.close()
            pages = ctx.pages
            self._page = pages[-1] if pages else None
            return "Tab closed."
        return "No active tab to close."

    async def screenshot(self, path: str = None) -> str:
        page = await self._get_page()
        try:
            save_path = path or str(Path.home() / "Desktop" / "jarvis_screenshot.png")
            await page.screenshot(path=save_path, full_page=False)
            return f"Screenshot saved: {save_path}"
        except Exception as e:
            return f"Screenshot error: {e}"

    async def back(self) -> str:
        page = await self._get_page()
        try:
            await page.go_back(timeout=10_000)
            return f"Navigated back: {page.url}"
        except Exception as e:
            return f"Back error: {e}"

    async def forward(self) -> str:
        page = await self._get_page()
        try:
            await page.go_forward(timeout=10_000)
            return f"Navigated forward: {page.url}"
        except Exception as e:
            return f"Forward error: {e}"

    async def reload(self) -> str:
        page = await self._get_page()
        try:
            await page.reload(timeout=15_000)
            return f"Page reloaded: {page.url}"
        except Exception as e:
            return f"Reload error: {e}"

    async def close_browser(self) -> str:
        await self._async_close()
        return f"{self.browser_name} closed."

class _SessionRegistry:
    """Manages all active browser sessions."""

    def __init__(self):
        self._sessions:        dict[str, _BrowserSession] = {}
        self._active_browser:  str                        = ""
        self._lock             = threading.Lock()
        self._last_native_url: str                        = ""

    def has(self, browser_name: str | None = None) -> bool:
        """Is there an active automation session for this browser (or any)?"""
        with self._lock:
            if not browser_name:
                return bool(self._sessions)
            name = _ALIASES.get(browser_name.lower().strip(), browser_name.lower().strip())
            return name in self._sessions

    def note_native_url(self, url: str) -> None:
        self._last_native_url = url

    def pop_native_url(self) -> str:
        """Returns the last natively-opened URL once (consumed to avoid repeats)."""
        url, self._last_native_url = self._last_native_url, ""
        return url

    def _get_or_create(self, browser_name: str) -> _BrowserSession:
        with self._lock:
            if browser_name not in self._sessions:
                sess = _BrowserSession(browser_name)
                sess.start()
                self._sessions[browser_name] = sess
                print(f"[Registry] New session: {browser_name}")
            return self._sessions[browser_name]

    def get(self, browser_name: str | None = None) -> _BrowserSession:
        if not browser_name:
            browser_name = self._active_browser or _detect_default_browser()
        browser_name = _ALIASES.get(browser_name.lower().strip(), browser_name.lower().strip())
        sess = self._get_or_create(browser_name)
        self._active_browser = browser_name
        return sess

    def switch(self, browser_name: str) -> str:
        browser_name = _ALIASES.get(browser_name.lower().strip(), browser_name.lower().strip())
        self._get_or_create(browser_name)
        self._active_browser = browser_name
        return f"Active browser → {browser_name}"

    def close_one(self, browser_name: str) -> str:
        with self._lock:
            sess = self._sessions.pop(browser_name, None)
        if sess:
            sess.close()
            if self._active_browser == browser_name:
                self._active_browser = ""
            return f"{browser_name} closed."
        return f"No active session for: {browser_name}"

    def close_all(self) -> str:
        with self._lock:
            names    = list(self._sessions.keys())
            sessions = list(self._sessions.values())
            self._sessions.clear()
            self._active_browser = ""
        for s in sessions:
            try:
                s.close()
            except Exception:
                pass
        return "All browsers closed: " + (", ".join(names) if names else "none")

    def list_sessions(self) -> str:
        with self._lock:
            if not self._sessions:
                return "No active browser sessions."
            lines = []
            for name in self._sessions:
                marker = " < active" if name == self._active_browser else ""
                lines.append(f"  * {name}{marker}")
            return "Open browsers:\n" + "\n".join(lines)


def _focus_active_browser(browser_name: str | None = None) -> bool:
    """Brings the user's browser window to the foreground so clicks and vision land on the right window."""
    try:
        from actions.computer_control import _focus_window
        candidates = []
        if browser_name:
            candidates.append(browser_name)
        detected = _detect_default_browser()
        if detected:
            candidates.append(detected)
        candidates.extend(["chrome", "msedge", "edge", "brave", "firefox", "opera"])

        seen = set()
        for name in candidates:
            if not name or name in seen:
                continue
            seen.add(name)
            res = _focus_window(name)
            if "Focused" in res:
                time.sleep(0.2)
                return True
    except Exception:
        pass
    return False


def _desktop_screen_click(description: str = "", text: str = "", browser_name: str | None = None) -> str:
    target = description or text
    if not target or target.strip() in ("", "button", "kisi button"):
        target = "any button"

    # Ensure browser window is focused before screen search
    _focus_active_browser(browser_name)

    try:
        from actions.computer_control import _screen_find, _click
        coords = _screen_find(target)
        if coords:
            time.sleep(0.15)
            _click(coords[0], coords[1])
            return f"Clicked '{target}' on screen at {coords}"
    except Exception as e:
        print(f"[Browser] Desktop screen click error: {e}")
    return f"Could not find element on screen: '{target}'"


def _desktop_fill_field(
    description: str = "",
    text: str = "",
    clear_first: bool = True,
    press_enter: bool = False,
) -> str:
    try:
        from actions.computer_control import _fill_input
        return _fill_input(
            description=description,
            text=text,
            clear_first=clear_first,
            press_enter=press_enter,
        )
    except Exception as e:
        print(f"[Browser] Desktop fill field error: {e}")
        return f"Desktop fill field error: {e}"


def _desktop_scroll(direction: str = "down", amount: int = 500) -> str:
    try:
        from actions.computer_control import _scroll
        # Convert pixel scroll amount to wheel notches
        clicks = int(amount // 80) if amount >= 80 else int(amount)
        return _scroll(direction=direction, amount=max(1, clicks))
    except Exception as e:
        return f"Desktop scroll error: {e}"


_registry = _SessionRegistry()

def browser_control(
    parameters:    dict = None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params  = parameters or {}
    action  = params.get("action", "").lower().strip()
    browser = params.get("browser", "").lower().strip() or None
    result  = "Unknown action."

    if action == "switch":
        target = browser or params.get("target", "").lower().strip()
        result = _registry.switch(target) if target else "Please specify a browser."
        _log(player, result)
        return result

    if action == "list_browsers":
        result = _registry.list_sessions()
        _log(player, result)
        return result

    if action == "close_all":
        result = _registry.close_all()
        _log(player, result)
        return result

    if action == "close":
        target = browser or _registry._active_browser
        if target:
            result = _registry.close_one(target)
        else:
            # Native opens (YouTube, Google, etc.) intentionally do not create
            # a Playwright session. Fall back to the universal window closer so
            # a spoken "close YouTube" actually closes the visible tab.
            try:
                from actions.close_application import close_application
                native_target = params.get("target") or "browser"
                result = close_application({"target": native_target}, player=player)
            except Exception as e:
                result = f"Could not close browser: {e}"
        _log(player, result)
        return result

    # ── Navigation ───────────────────────────────────────────────────────────
    # If automated=True or control=True or an automated session already exists,
    # open via Playwright so that all DOM elements and buttons can be clicked/inspected.
    # Otherwise open natively in user's browser.
    if action in ("go_to", "search", "new_tab"):
        use_automation = params.get("automated") or params.get("control") or _registry.has(browser)
        if use_automation:
            sess = _registry.get(browser)
            try:
                if action == "search":
                    result = sess.run(sess.search(params.get("query", ""),
                                                  params.get("engine", "google")))
                elif action == "new_tab":
                    result = sess.run(sess.new_tab(params.get("url", "")))
                else:
                    result = sess.run(sess.go_to(params.get("url", "")))
            except concurrent.futures.TimeoutError:
                result = f"Browser action '{action}' timed out (60s)."
            except Exception as e:
                result = f"Browser error ({action}): {e}"
            _log(player, result)
            return result

        if action == "search":
            base    = _SEARCH_ENGINES.get(params.get("engine", "google").lower(),
                                          _SEARCH_ENGINES["google"])
            nav_url = base + params.get("query", "").replace(" ", "+")
        else:
            nav_url = params.get("url", "").strip()

        result = _open_native(nav_url, browser)
        if result.startswith("Opened") and nav_url:
            _registry.note_native_url(_normalize_url(nav_url))
        _log(player, result)
        return result

    # ── Interactive actions (click/type/scroll/fill/read/scan...) ─────────────
    # Auto-detect if Chrome is running with remote debugging port (CDP)
    if not _registry.has(browser):
        try:
            import urllib.request
            req = urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=0.3)
            if req.status == 200:
                _registry._get_or_create(browser or "chrome")
        except Exception:
            pass

    has_active_sess = _registry.has(browser)

    if action in ("scan_elements", "list_elements", "get_elements", "list_buttons", "show_buttons"):
        if has_active_sess:
            try:
                sess = _registry.get(browser)
                elements = sess.run(sess.get_all_clickable_elements())
                if elements:
                    texts = [e["text"] for e in elements if e.get("text")]
                    unique_texts = list(dict.fromkeys(texts))[:15]
                    result = f"Visible buttons & elements on page ({len(unique_texts)}): " + ", ".join(f"'{t}'" for t in unique_texts)
                    _log(player, result)
                    return result
                result = "No visible clickable elements detected on current page."
                _log(player, result)
                return result
            except Exception as e:
                result = f"Error scanning elements: {e}"
                _log(player, result)
                return result

        result = "Page is open in regular browser. I can click any visible button via screen vision, or open in automated browser to inspect full DOM tree."
        _log(player, result)
        return result

    if action == "scroll":
        result_parts = []
        if has_active_sess:
            try:
                sess = _registry.get(browser)
                res = sess.run(sess.scroll(params.get("direction", "down"), int(params.get("amount", 500))))
                result_parts.append(res)
            except Exception:
                pass
        d_res = _desktop_scroll(params.get("direction", "down"), int(params.get("amount", 500)))
        result_parts.append(d_res)
        result = " | ".join(result_parts) if result_parts else d_res
        _log(player, result)
        return result

    if action in ("click", "smart_click", "trigger"):
        target_desc = params.get("description") or params.get("text") or ""
        selector = params.get("selector")

        # 1. Try Playwright if active
        if has_active_sess:
            try:
                sess = _registry.get(browser)
                res = sess.run(sess.click(selector=selector, text=params.get("text"), description=params.get("description")))
                if not any(k in res.lower() for k in ("could not find", "not found", "error", "timeout")):
                    _log(player, res)
                    return res
            except Exception as e:
                print(f"[Browser] Playwright click attempt failed: {e}")

        # 2. Desktop screen vision fallback
        result = _desktop_screen_click(description=target_desc, text=params.get("text", ""), browser_name=browser)
        _log(player, result)
        return result

    if action in ("type", "smart_type", "fill_field", "fill_input"):
        text = params.get("text", "")
        desc = params.get("description") or params.get("selector") or ""
        clear_first = params.get("clear_first", True)
        press_enter = params.get("press_enter", False)

        # 1. Try Playwright if active
        if has_active_sess:
            try:
                sess = _registry.get(browser)
                res = sess.run(sess.type_text(
                    selector=params.get("selector"),
                    text=text,
                    clear_first=clear_first,
                    description=params.get("description"),
                    press_enter=press_enter,
                ))
                if not any(k in res.lower() for k in ("could not find", "not found", "error")):
                    _log(player, res)
                    return res
            except Exception as e:
                print(f"[Browser] Playwright type attempt failed: {e}")

        # 2. Desktop input fill fallback
        result = _desktop_fill_field(
            description=desc,
            text=text,
            clear_first=clear_first,
            press_enter=press_enter,
        )
        _log(player, result)
        return result

    if action == "fill_form":
        fields = params.get("fields", {})
        if has_active_sess:
            try:
                sess = _registry.get(browser)
                res = sess.run(sess.fill_form(fields))
                _log(player, res)
                return res
            except Exception:
                pass

        results = []
        for f_desc, f_val in fields.items():
            r = _desktop_fill_field(description=f_desc, text=str(f_val))
            results.append(r)
        result = "Form filled: " + ", ".join(results)
        _log(player, result)
        return result

    if action == "press" and not has_active_sess:
        try:
            from actions.computer_control import _press
            result = _press(params.get("key", "enter"))
            _log(player, result)
            return result
        except Exception:
            pass

    # For other deep browser actions (get_text, get_url, screenshot, navigation history...)
    try:
        sess = _registry.get(browser)
    except Exception as e:
        result = f"Could not start browser session: {e}"
        _log(player, result)
        return result

    try:
        last = _registry.pop_native_url()
        if last:
            try:
                sess.run(sess.go_to(last))
            except Exception as e:
                print(f"[Browser] Could not resume last page ({last}): {e}")

        if action == "get_text":
            result = sess.run(sess.get_text())
        elif action == "get_url":
            result = sess.run(sess.get_url())
        elif action == "press":
            result = sess.run(sess.press(params.get("key", "Enter")))
        elif action == "close_tab":
            result = sess.run(sess.close_tab())
        elif action == "screenshot":
            result = sess.run(sess.screenshot(params.get("path")))
        elif action == "back":
            result = sess.run(sess.back())
        elif action == "forward":
            result = sess.run(sess.forward())
        elif action == "reload":
            result = sess.run(sess.reload())
        else:
            result = f"Unknown browser action: '{action}'"

    except concurrent.futures.TimeoutError:
        result = f"Browser action '{action}' timed out (60s)."
    except Exception as e:
        result = f"Browser error ({action}): {e}"

    _log(player, result)
    return result


def _log(player, text: str):
    short = str(text)[:80]
    print(f"[Browser] {short}")
    if player:
        player.write_log(f"[browser] {short[:60]}")


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "browser_control",
    "description": "Controls any web browser. Use for: opening websites, searching the web, clicking elements/buttons/links, filling input fields/forms, scrolling up/down, screenshots, navigation, tabs, and any web-based task. Works seamlessly with both automated and regular user browser windows.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "go_to | search | click | type | scroll | fill_field | fill_form | smart_click | smart_type | scan_elements | list_elements | get_text | get_url | press | new_tab | close_tab | screenshot | back | forward | reload | switch | list_browsers | close | close_all"
            },
            "automated": {
                "type": "BOOLEAN",
                "description": "Set true when opening websites to give JARVIS direct DOM element inspection and button trigger capabilities"
            },
            "browser": {
                "type": "STRING",
                "description": "Target browser: chrome | edge | firefox | opera | operagx | brave | vivaldi | safari. Omit to use the currently active browser."
            },
            "url": {
                "type": "STRING",
                "description": "URL for go_to / new_tab action"
            },
            "query": {
                "type": "STRING",
                "description": "Search query for search action"
            },
            "engine": {
                "type": "STRING",
                "description": "Search engine: google | bing | duckduckgo | yandex (default: google)"
            },
            "selector": {
                "type": "STRING",
                "description": "CSS selector for click/type"
            },
            "text": {
                "type": "STRING",
                "description": "Text to click or type into input field"
            },
            "description": {
                "type": "STRING",
                "description": "Natural description of button, link, or input field to click or fill (e.g. 'search bar', 'sign in button', 'email address', 'add to cart')"
            },
            "direction": {
                "type": "STRING",
                "description": "up | down for scroll"
            },
            "amount": {
                "type": "INTEGER",
                "description": "Scroll amount in pixels (default: 500)"
            },
            "press_enter": {
                "type": "BOOLEAN",
                "description": "Press enter key after typing into field (default: false)"
            },
            "key": {
                "type": "STRING",
                "description": "Key name for press action (e.g. Enter, Escape, F5)"
            },
            "path": {
                "type": "STRING",
                "description": "Save path for screenshot"
            },
            "incognito": {
                "type": "BOOLEAN",
                "description": "Open in private/incognito mode"
            },
            "clear_first": {
                "type": "BOOLEAN",
                "description": "Clear field before typing (default: true)"
            }
        },
        "required": [
            "action"
        ]
    },
    "handler": browser_control,
}
