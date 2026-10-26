#!/usr/bin/env python3
"""Client-side, input-only control for a running Factorio client.

This module deliberately does NOT inject a DLL, patch memory, or modify game
state.  It acts through normal Windows keyboard/mouse input and screenshots,
so it works against servers that have no AgentBridge scenario or RCON (for
example a vanilla freeplay host).  It is slower and less precise than the
server-side scenario; use it when server cooperation is unavailable.

Requirements:
  - Windows, Factorio running in a visible window, windowed mode recommended.
  - The game window must be foreground for input.  `focus()` uses
    AttachThreadInput to work around Windows' foreground lock.
  - Optional: `um win shot` for GPU-render-safe screenshots.  Without it the
    fallback is PIL.ImageGrab (may be black for some GPU windows).
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import json
import re
import subprocess
import time
from dataclasses import dataclass, asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
USER32 = ctypes.windll.user32

VK = {
    "w": 0x57, "a": 0x41, "s": 0x53, "d": 0x44,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "e": 0x45, "m": 0x4D, "q": 0x51, "r": 0x52, "t": 0x54,
    "tab": 0x09, "esc": 0x1B, "enter": 0x0D, "space": 0x20,
    "shift": 0x10, "ctrl": 0x11, "alt": 0x12,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73,
    "tilde": 0xC0, "grave": 0xC0, "minus": 0xBD, "plus": 0xBB,
    "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34, "5": 0x35,
    "6": 0x36, "7": 0x37, "8": 0x38, "9": 0x39, "0": 0x30,
}
VK_NAME = {v: k for k, v in VK.items()}


def _title(hwnd: int) -> str:
    n = USER32.GetWindowTextLengthW(hwnd)
    if n <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(n + 1)
    USER32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def _pid(hwnd: int) -> int:
    p = wt.DWORD()
    USER32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
    return int(p.value)


def find_windows(title_regex: str = r"(?i)factorio", pid: int | None = None) -> list[dict]:
    """List visible top-level windows matching a title regex and/or PID."""
    pattern = re.compile(title_regex) if title_regex else None
    out: list[dict] = []
    EnumProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

    def cb(hwnd, _):
        if not USER32.IsWindowVisible(hwnd):
            return True
        t = _title(hwnd)
        if not t:
            return True
        owner = _pid(hwnd)
        if pid is not None and owner != pid:
            return True
        if pattern and not pattern.search(t):
            return True
        out.append({"hwnd": int(hwnd), "pid": owner, "title": t})
        return True

    USER32.EnumWindows(EnumProc(cb), 0)
    return out


@dataclass
class WindowInfo:
    hwnd: int
    pid: int
    title: str


class ClientController:
    def __init__(self, hwnd: int | None = None, pid: int | None = None,
                 title_regex: str = r"(?i)factorio"):
        self.hwnd = hwnd
        self.pid = pid
        self.title_regex = title_regex
        if self.hwnd is None:
            matches = find_windows(title_regex, pid)
            if not matches:
                raise RuntimeError(
                    f"no visible Factorio window (title/{title_regex!r}, pid={pid})")
            self.hwnd = matches[0]["hwnd"]
            self.pid = matches[0]["pid"]
        else:
            self.pid = _pid(self.hwnd)

    # -- window ------------------------------------------------------------
    def info(self) -> dict:
        return {"hwnd": self.hwnd, "pid": self.pid, "title": _title(self.hwnd),
                "foreground": USER32.GetForegroundWindow() == self.hwnd,
                "client_rect": self.client_rect()}

    def client_rect(self) -> dict:
        r = wt.RECT()
        USER32.GetClientRect(self.hwnd, ctypes.byref(r))
        pt = wt.POINT(0, 0)
        USER32.ClientToScreen(self.hwnd, ctypes.byref(pt))
        return {"left": pt.x, "top": pt.y,
                "width": r.right - r.left, "height": r.bottom - r.top}

    def focus(self) -> dict:
        """Restore and force the window to the foreground.

        Windows normally rejects SetForegroundWindow from a background process;
        temporarily attaching to the foreground thread's input queue bypasses
        that for the duration of this call.
        """
        USER32.ShowWindow(self.hwnd, 9)  # SW_RESTORE
        fg = USER32.GetForegroundWindow()
        tf = USER32.GetWindowThreadProcessId(fg, None)
        tt = USER32.GetWindowThreadProcessId(self.hwnd, None)
        USER32.AttachThreadInput(tf, tt, True)
        try:
            USER32.BringWindowToTop(self.hwnd)
            USER32.SetForegroundWindow(self.hwnd)
        finally:
            USER32.AttachThreadInput(tf, tt, False)
        time.sleep(0.15)
        info = self.info()
        info["ok"] = bool(info.get("foreground"))
        return info

    def _require_foreground(self) -> None:
        if USER32.GetForegroundWindow() != self.hwnd:
            raise RuntimeError("Factorio window is not foreground; call focus() "
                               "and do not switch windows while input is held")

    # -- input -------------------------------------------------------------
    @staticmethod
    def vk(key: int | str) -> int:
        if isinstance(key, int):
            return key
        k = str(key).lower().lstrip("vk")
        if k in VK:
            return VK[k]
        if re.fullmatch(r"0x[0-9a-f]+", k):
            return int(k, 16)
        if len(k) == 1:
            return ord(k.upper())
        raise ValueError(f"unknown key {key!r}")

    def key(self, key: int | str, action: str = "tap") -> dict:
        vk = self.vk(key)
        self._require_foreground()
        if action == "down":
            USER32.keybd_event(vk, 0, 0, 0)
        elif action == "up":
            USER32.keybd_event(vk, 0, 2, 0)
        elif action == "tap":
            USER32.keybd_event(vk, 0, 0, 0)
            time.sleep(0.04)
            USER32.keybd_event(vk, 0, 2, 0)
        else:
            raise ValueError("action must be tap/down/up")
        return {"ok": True, "key": VK_NAME.get(vk, hex(vk)), "action": action}

    def hold(self, key: int | str, ms: int = 500, check_focus: bool = True) -> dict:
        vk = self.vk(key)
        self._require_foreground()
        USER32.keybd_event(vk, 0, 0, 0)
        start = time.time()
        try:
            while (time.time() - start) * 1000 < ms:
                if check_focus and USER32.GetForegroundWindow() != self.hwnd:
                    raise RuntimeError("foreground changed during hold; input aborted")
                time.sleep(0.03)
        finally:
            USER32.keybd_event(vk, 0, 2, 0)
        return {"ok": True, "key": VK_NAME.get(vk, hex(vk)), "ms": ms}

    def walk(self, direction: str, seconds: float = 1.0) -> dict:
        d = str(direction).lower()
        mapping = {"up": "w", "down": "s", "left": "a", "right": "d",
                   "north": "w", "south": "s", "west": "a", "east": "d"}
        return self.hold(mapping.get(d, d), int(max(0.05, seconds) * 1000))

    def click(self, x: float, y: float, button: str = "left",
              hold_ms: int = 0, double: bool = False) -> dict:
        self._require_foreground()
        r = self.client_rect()
        sx, sy = int(r["left"] + x), int(r["top"] + y)
        USER32.SetCursorPos(sx, sy)
        time.sleep(0.05)
        down, up = (0x0002, 0x0004) if button.lower() == "right" else (0x0001, 0x0004)
        if double:
            for _ in range(2):
                USER32.mouse_event(down, 0, 0, 0, 0)
                USER32.mouse_event(up, 0, 0, 0, 0)
                time.sleep(0.08)
            return {"ok": True, "x": x, "y": y, "button": button, "double": True}
        USER32.mouse_event(down, 0, 0, 0, 0)
        if hold_ms:
            start = time.time()
            try:
                while (time.time() - start) * 1000 < hold_ms:
                    if USER32.GetForegroundWindow() != self.hwnd:
                        raise RuntimeError("foreground changed during click hold")
                    time.sleep(0.03)
            finally:
                USER32.mouse_event(up, 0, 0, 0, 0)
        else:
            time.sleep(0.05)
            USER32.mouse_event(up, 0, 0, 0, 0)
        return {"ok": True, "x": x, "y": y, "button": button, "hold_ms": hold_ms}

    def scroll(self, amount: int = 120) -> dict:
        self._require_foreground()
        USER32.mouse_event(0x0800, 0, 0, int(amount), 0)
        return {"ok": True, "amount": amount}

    def type_text(self, text: str) -> dict:
        """Type ASCII text using normal key events (for console/chat)."""
        self._require_foreground()
        for ch in str(text):
            if ch == "\n":
                self.key("enter")
                continue
            if ch == "\t":
                self.key("tab")
                continue
            vk = USER32.VkKeyScanW(ord(ch))
            if vk == -1:
                raise ValueError(f"character not typeable: {ch!r}")
            vk = vk & 0xFF
            shift = bool((USER32.VkKeyScanW(ord(ch)) >> 8) & 1)
            if shift:
                USER32.keybd_event(0x10, 0, 0, 0)
            USER32.keybd_event(vk, 0, 0, 0)
            time.sleep(0.01)
            USER32.keybd_event(vk, 0, 2, 0)
            if shift:
                USER32.keybd_event(0x10, 0, 2, 0)
        return {"ok": True, "chars": len(str(text))}

    # -- screenshots -------------------------------------------------------
    def screenshot(self, output: str | Path, scale: float | None = None,
                   prefer_um: bool = True) -> dict:
        out = Path(output).expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        if prefer_um:
            try:
                cmd = ["um", "win", "shot", "--hwnd", str(self.hwnd)]
                if scale:
                    cmd += ["--scale", str(scale)]
                cmd.append(str(out))
                p = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if p.returncode == 0 and out.exists():
                    small = out.with_name(out.stem + "_small" + out.suffix)
                    result = {"ok": True, "path": str(out), "hwnd": self.hwnd,
                              "backend": "um-gfxcapture"}
                    if small.exists():
                        result["small"] = str(small)
                    return result
            except (FileNotFoundError, subprocess.SubprocessError):
                pass
        try:
            from PIL import ImageGrab  # optional, may be black on GPU windows
            r = self.client_rect()
            img = ImageGrab.grab(bbox=(r["left"], r["top"],
                                        r["left"] + r["width"],
                                        r["top"] + r["height"]))
            img.save(out)
            return {"ok": True, "path": str(out), "hwnd": self.hwnd,
                    "backend": "PIL.ImageGrab", "warning": "may be black for GPU windows"}
        except Exception as e:
            raise RuntimeError(f"screenshot failed: {e}; install `um`/ffmpeg gfxcapture") from e

    # -- convenience -------------------------------------------------------
    def map_toggle(self) -> dict:
        return self.key("m")

    def inventory_toggle(self) -> dict:
        return self.key("e")

    def console_toggle(self) -> dict:
        return self.key("tilde")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _controller(a) -> ClientController:
    return ClientController(hwnd=a.hwnd, pid=a.pid, title_regex=a.title)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Input-only client-side Factorio control")
    ap.add_argument("--hwnd", type=int)
    ap.add_argument("--pid", type=int)
    ap.add_argument("--title", default=r"(?i)factorio")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list")
    p = sub.add_parser("info"); p.set_defaults(fn=lambda c: c.info())
    p = sub.add_parser("focus"); p.set_defaults(fn=lambda c: c.focus())
    p = sub.add_parser("shot"); p.add_argument("output"); p.add_argument("--scale", type=float)
    p.set_defaults(fn=lambda c, a: c.screenshot(a.output, a.scale))
    p = sub.add_parser("key"); p.add_argument("key"); p.add_argument("action", nargs="?", default="tap")
    p.set_defaults(fn=lambda c, a: c.key(a.key, a.action))
    p = sub.add_parser("hold"); p.add_argument("key"); p.add_argument("ms", type=int)
    p.set_defaults(fn=lambda c, a: c.hold(a.key, a.ms))
    p = sub.add_parser("walk"); p.add_argument("direction"); p.add_argument("seconds", type=float)
    p.set_defaults(fn=lambda c, a: c.walk(a.direction, a.seconds))
    p = sub.add_parser("click"); p.add_argument("x", type=float); p.add_argument("y", type=float)
    p.add_argument("--button", default="left"); p.add_argument("--hold-ms", type=int, default=0)
    p.add_argument("--double", action="store_true")
    p.set_defaults(fn=lambda c, a: c.click(a.x, a.y, a.button, a.hold_ms, a.double))
    p = sub.add_parser("type"); p.add_argument("text"); p.set_defaults(fn=lambda c, a: c.type_text(a.text))
    p = sub.add_parser("map"); p.set_defaults(fn=lambda c: c.map_toggle())
    p = sub.add_parser("inv"); p.set_defaults(fn=lambda c: c.inventory_toggle())

    a = ap.parse_args(argv)
    if a.cmd == "list":
        print(json.dumps(find_windows(a.title, a.pid), ensure_ascii=False, indent=2))
        return 0
    c = _controller(a)
    try:
        result = a.fn(c, a) if a.cmd in ("shot", "key", "hold", "walk", "click", "type") else a.fn(c)
    except TypeError:
        result = a.fn(c)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
