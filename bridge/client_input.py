#!/usr/bin/env python3
"""Probe SDL event injection in a running Factorio client (background input).

All game-touching calls are queued and executed from a hook that fires on the
game thread (SDL_PollEvent / luaD_call), never from the Frida RPC thread.
"""
from __future__ import annotations

import argparse
import json
import time

import frida

RVA = {
    "send_key": 0x1B504A0,          # SDL_SendKeyboardKeyInternal
    "get_keyboards": 0x1B4F980,     # SDL_GetKeyboards_REAL
    "get_keyboard_focus": 0x1B4FDF0,  # SDL_GetKeyboardFocus_REAL
    "set_keyboard_focus": 0x1B4FE00,  # SDL_SetKeyboardFocus
    "get_windows": 0x1B08960,       # SDL_GetWindows_REAL
    "get_window_id": 0x1B09A80,     # SDL_GetWindowID_REAL
    "get_window_size": 0x1B0A7B0,   # SDL_GetWindowSize_REAL
    "get_window_pos": 0x1B0A1F0,    # SDL_GetWindowPosition_REAL
    "get_window_flags": 0x1B09C30,  # SDL_GetWindowFlags_REAL
    "send_text": 0x1B50800,         # SDL_SendKeyboardText
    "push_event": 0x1B2F2A0,        # SDL_PushEvent_REAL
    "poll_event": 0x1B2E220,        # SDL_PollEvent_REAL
    "send_mouse_motion": 0x1ADC250,  # SDL_SendMouseMotion
    "send_mouse_wheel": 0x1ADCF40,  # SDL_SendMouseWheel
    "private_mouse_button": 0x1ADCB90,  # SDL_PrivateSendMouseButton
    "set_mouse_focus": 0x1ADC010,   # SDL_SetMouseFocus
    "get_mice": 0x1ADBC30,          # SDL_GetMice_REAL
    "get_mouse_focus": 0x1ADC000,   # SDL_GetMouseFocus_REAL
    "get_mouse_state": 0x1ADDB20,   # SDL_GetMouseState_REAL
    "warp_mouse": 0x1ADDC70,        # SDL_WarpMouseInWindow_REAL
    "ticks_ns": 0x1AF18D0,          # SDL_GetTicksNS_REAL
    "luaD_call": 0x1D137E0,         # game thread pump
    "sdl_mouse_focus": 0x2D32998,
    "sdl_mouse_x": 0x2D329A0,
    "sdl_mouse_y": 0x2D329A4,
    "sdl_mouse_count": 0x2D32A12,
    "sdl_mouse_arr": 0x2D32A18,
}

JS = r"""
const rva = %(rva)s;
const mod = Process.enumerateModules().find(m => m.name.toLowerCase() === 'factorio.exe');
if (!mod) throw new Error('factorio.exe not found');
const base = mod.base;
const p = {};
for (const k in rva) p[k] = base.add(rva[k]);
const f = {
  sendKey: new NativeFunction(p.send_key, 'bool', ['uint64','uint32','uint32','int','int','bool']),
  getKeyboards: new NativeFunction(p.get_keyboards, 'pointer', ['pointer']),
  getFocus: new NativeFunction(p.get_keyboard_focus, 'pointer', []),
  setFocus: new NativeFunction(p.set_keyboard_focus, 'bool', ['pointer']),
  getWindows: new NativeFunction(p.get_windows, 'pointer', ['pointer']),
  getWindowId: new NativeFunction(p.get_window_id, 'uint32', ['pointer']),
  getWindowSize: new NativeFunction(p.get_window_size, 'bool', ['pointer','pointer','pointer']),
  getWindowPos: new NativeFunction(p.get_window_pos, 'bool', ['pointer','pointer','pointer']),
  getWindowFlags: new NativeFunction(p.get_window_flags, 'uint64', ['pointer']),
  sendText: new NativeFunction(p.send_text, 'bool', ['pointer']),
  pushEvent: new NativeFunction(p.push_event, 'bool', ['pointer']),
  sendMouseMotion: new NativeFunction(p.send_mouse_motion, 'bool', ['uint64','pointer','uint32','bool','float','float']),
  sendMouseWheel: new NativeFunction(p.send_mouse_wheel, 'bool', ['uint64','pointer','uint32','float','float','int']),
  privateMouseButton: new NativeFunction(p.private_mouse_button, 'void', ['uint64','pointer','uint32','uint8','bool','int']),
  setMouseFocus: new NativeFunction(p.set_mouse_focus, 'bool', ['pointer']),
  getMice: new NativeFunction(p.get_mice, 'pointer', ['pointer']),
  getMouseFocus: new NativeFunction(p.get_mouse_focus, 'pointer', []),
  getMouseState: new NativeFunction(p.get_mouse_state, 'uint32', ['pointer','pointer']),
  warpMouse: new NativeFunction(p.warp_mouse, 'bool', ['pointer','float','float']),
  ticksNs: new NativeFunction(p.ticks_ns, 'uint64', []),
};
let queue = [];
let busy = false;
let pumped = 0;
let lastHook = 'none';
function pump(hook) {
  if (busy) return;
  if (hook) lastHook = hook;
  if (!queue.length) return;
  busy = true;
  const job = queue.shift();
  pumped++;
  try { job.resolve(job.fn()); }
  catch (e) { job.reject({message: String(e), stack: e && e.stack ? String(e.stack) : null}); }
  finally { busy = false; }
}
function run(fn, timeoutMs) {
  return new Promise((resolve, reject) => {
    const job = {fn, resolve, reject};
    queue.push(job);
    setTimeout(() => {
      if (queue.includes(job)) {
        queue = queue.filter(j => j !== job);
        reject({message: 'timeout waiting for game thread', queue: queue.length, pumped, lastHook});
      }
    }, timeoutMs || 5000);
  });
}
function windowInfo(w) {
  if (!w || w.isNull()) return null;
  const wp = Memory.alloc(4), hp = Memory.alloc(4);
  const xp = Memory.alloc(4), yp = Memory.alloc(4);
  const ok = f.getWindowSize(w, wp, hp);
  f.getWindowPos(w, xp, yp);
  return { ptr: w.toString(), id: f.getWindowId(w), w: wp.readS32(), h: hp.readS32(),
           x: xp.readS32(), y: yp.readS32(), flags: '0x' + f.getWindowFlags(w).toString(16), ok };
}
function collect() {
  const count = Memory.alloc(4);
  const winArr = f.getWindows(count);
  const n = count.readS32();
  const windows = [];
  for (let i = 0; i < n; i++) windows.push(windowInfo(winArr.add(i * Process.pointerSize).readPointer()));
  const kbCount = Memory.alloc(4);
  const kbArr = f.getKeyboards(kbCount);
  const kn = kbCount.readS32();
  const keyboards = [];
  for (let i = 0; i < kn; i++) keyboards.push(kbArr.add(i * 4).readU32());
  const mouseCount = Memory.alloc(4);
  const mouseArr = f.getMice(mouseCount);
  const mn = mouseCount.readS32();
  const mice = [];
  for (let i = 0; i < mn; i++) mice.push(mouseArr.add(i * 4).readU32());
  return { focus: f.getFocus().toString(), mouseFocus: f.getMouseFocus().toString(),
           windows, keyboards, mice, ticksNs: f.ticksNs().toString(), pumped, lastHook };
}
function firstWindow() {
  const count = Memory.alloc(4);
  const arr = f.getWindows(count);
  const n = count.readS32();
  return n > 0 ? arr.readPointer() : null;
}
function firstKeyboard() {
  const count = Memory.alloc(4);
  const arr = f.getKeyboards(count);
  const n = count.readS32();
  return n > 0 ? arr.readU32() : 0;
}
let vm = { active: false, x: 0, y: 0, win: null, buttons: 0 };
let winID = 0;
function pushWindowEvent(type, windowID) {
  try {
    const ev = Memory.alloc(128);
    Memory.writeByteArray(ev, new Uint8Array(128));
    ev.writeU32(type);
    ev.writeU64(uint64(0), 8);
    ev.writeU32(windowID, 16);
    return f.pushEvent(ev);
  } catch (e) { return false; }
}
function setFocusFlags(w) {
  try {
    const f1 = w.add(0x48).readU64();
    const f2 = w.add(0x50).readU64();
    w.add(0x48).writeU64(f1.or(0x400));
    w.add(0x50).writeU64(f2.or(0x400));
  } catch (e) {}
}
function syncSdlMouse() {
  if (!vm.active) return;
  try {
    if (vm.win) setFocusFlags(vm.win);
    p.sdl_mouse_focus.writePointer(vm.win || ptr(0));
    p.sdl_mouse_x.writeFloat(vm.x);
    p.sdl_mouse_y.writeFloat(vm.y);
    const n = p.sdl_mouse_count.readS32();
    if (n > 0) {
      const arr = p.sdl_mouse_arr.readPointer();
      if (!arr.isNull()) arr.add(4).writeU32(vm.buttons >>> 0);
    }
  } catch (e) {}
}
function replaceMouse(ev) {
  if (!vm.active || !ev || ev.isNull()) return;
  try {
    const type = ev.readU32();
    if (type === 0x20d || type === 0x20f) {  // MOUSE_LEAVE / FOCUS_LOST while virtual mouse active
      ev.writeU32(0x204);  // turn into a harmless WINDOW_EXPOSED
      return;
    }
    if (type === 0x400 || type === 0x401 || type === 0x402) {
      const ox = ev.add(28).readFloat();
      const oy = ev.add(32).readFloat();
      if (Math.abs(ox - vm.x) > 1.0 || Math.abs(oy - vm.y) > 1.0) {
        ev.writeU32(0x204);  // drop real mouse events while virtual mouse is active
        return;
      }
      if (winID === 0) { const w = firstWindow(); if (w) winID = f.getWindowId(w); }
      if (winID) ev.add(16).writeU32(winID);
      ev.add(28).writeFloat(vm.x);
      ev.add(32).writeFloat(vm.y);
      if (type === 0x400) ev.add(24).writeU32(vm.buttons >>> 0);
    }
  } catch (e) {}
}
Interceptor.attach(p.luaD_call, { onLeave(retval) { pump('luaD_call'); } });
Interceptor.attach(p.poll_event, {
  onEnter(args) { this.ev = args[0]; },
  onLeave(retval) {
    if (retval.toInt32() === 1) replaceMouse(this.ev);
    syncSdlMouse();
    pump('SDL_PollEvent');
  }
});
rpc.exports = {
  sdlInfo() { return run(collect, 5000); },
  diag() { return { queue: queue.length, pumped, lastHook, focus: f.getFocus().toString() }; },
  focusWindow() {
    return run(() => {
      const w = firstWindow();
      if (!w) throw new Error('no SDL window');
      const before = f.getFocus().toString();
      const ok = f.setFocus(w);
      return { ok, before, after: f.getFocus().toString(), win: windowInfo(w) };
    });
  },
  key(scancode, down) {
    return run(() => {
      let w = f.getFocus();
      if (w.isNull()) w = firstWindow();
      return { ok: f.sendKey(uint64(0), 0, firstKeyboard(), 0, Number(scancode), down ? 1 : 0),
               focus: f.getFocus().toString(), win: w ? w.toString() : null };
    });
  },
  text(s) {
    return run(() => ({ ok: f.sendText(Memory.allocUtf8String(s)) }));
  },
  mouseMove(x, y, relative) {
    return run(() => {
      let w = f.getFocus();
      if (w.isNull()) w = firstWindow();
      const count = Memory.alloc(4);
      const m = f.getMice(count);
      const mouseID = count.readS32() > 0 ? m.readU32() : 0;
      f.setMouseFocus(w);
      const ok = f.sendMouseMotion(uint64(0), w, 0, 0, Number(x), Number(y));
      return { ok, mouseID, focus: f.getFocus().toString(), mouseFocus: f.getMouseFocus().toString() };
    });
  },
  mouseButton(button, down, clicks) {
    return run(() => {
      let w = f.getFocus();
      if (w.isNull()) w = firstWindow();
      const count = Memory.alloc(4);
      const m = f.getMice(count);
      const mouseID = count.readS32() > 0 ? m.readU32() : 0;
      vm.win = w;
      vm.active = true;
      const bit = button === 1 ? 1 : button === 2 ? 2 : button === 3 ? 4 : 0;
      if (bit) { if (down) vm.buttons |= bit; else vm.buttons &= ~bit; }
      f.setMouseFocus(w);
      syncSdlMouse();
      f.privateMouseButton(uint64(0), w, mouseID, button, down ? 1 : 0, clicks === undefined ? 1 : clicks);
      syncSdlMouse();
      return { mouseID, buttons: vm.buttons, mouseFocus: f.getMouseFocus().toString() };
    });
  },
  vmEnable(x, y) {
    return run(() => {
      let w = f.getFocus();
      if (w.isNull()) w = firstWindow();
      vm.active = true; vm.x = x; vm.y = y; vm.win = w; vm.buttons = 0;
      f.setMouseFocus(w);
      f.setFocus(w);
      setFocusFlags(w);
      if (winID === 0) winID = f.getWindowId(w);
      pushWindowEvent(0x20c, winID);  // MOUSE_ENTER
      pushWindowEvent(0x20e, winID);  // FOCUS_GAINED
      syncSdlMouse();
      f.sendMouseMotion(uint64(0), w, 0, 0, x, y);
      return { active: vm.active, x: vm.x, y: vm.y, winID, focus: f.getFocus().toString(), mouseFocus: f.getMouseFocus().toString() };
    });
  },
  vmMove(x, y) {
    return run(() => {
      vm.active = true; vm.x = x; vm.y = y;
      let w = f.getFocus();
      if (w.isNull()) w = firstWindow();
      vm.win = w;
      f.setMouseFocus(w);
      setFocusFlags(w);
      syncSdlMouse();
      const ok = f.sendMouseMotion(uint64(0), w, 0, 0, x, y);
      return { ok, active: vm.active, x: vm.x, y: vm.y, winID };
    });
  },
  vmDisable() {
    return run(() => { vm.active = false; return { active: false }; });
  },
  vmState() { return { active: vm.active, x: vm.x, y: vm.y, winID, buttons: vm.buttons }; },
  vmWake() {
    return run(() => {
      let w = f.getFocus();
      if (w.isNull()) w = firstWindow();
      vm.win = w; vm.active = true;
      if (winID === 0) winID = f.getWindowId(w);
      f.setMouseFocus(w); f.setFocus(w); setFocusFlags(w);
      const a = pushWindowEvent(0x20c, winID);
      const b = pushWindowEvent(0x20e, winID);
      syncSdlMouse();
      return { a, b, winID, focus: f.getFocus().toString(), mouseFocus: f.getMouseFocus().toString() };
    });
  },
  sdlMouseRaw() {
    return run(() => {
      const n = p.sdl_mouse_count.readS32();
      const arr = p.sdl_mouse_arr.readPointer();
      let rawButtons = null;
      if (n > 0 && !arr.isNull()) rawButtons = arr.add(4).readU32();
      return { focus: p.sdl_mouse_focus.readPointer().toString(), x: p.sdl_mouse_x.readFloat(),
               y: p.sdl_mouse_y.readFloat(), count: n, rawButtons };
    });
  },
  mouseState() {
    return run(() => {
      const xp = Memory.alloc(4), yp = Memory.alloc(4);
      const buttons = f.getMouseState(xp, yp);
      return { buttons, x: xp.readFloat(), y: yp.readFloat(), mouseFocus: f.getMouseFocus().toString() };
    });
  },
  mouseWheel(x, y) {
    return run(() => {
      const w = f.getFocus();
      return { ok: f.sendMouseWheel(0, w, 0, x, y, 0) };
    });
  },
};
""" % {"rva": json.dumps(RVA)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, required=True)
    ap.add_argument("cmd", choices=["info", "focus", "walk", "key", "text", "mousemove", "mousedown", "mouseup", "click", "mousestate", "vmenable", "vmmove", "vmdisable", "vmstate", "sdlmouseraw", "diag"])
    ap.add_argument("args", nargs="*")
    a = ap.parse_args()
    session = frida.attach(a.pid)
    script = session.create_script(JS)
    messages = []
    script.on("message", lambda m, d: messages.append(m))
    script.load()
    ex = script.exports_sync
    try:
        if a.cmd == "info":
            print(json.dumps(ex.sdl_info(), indent=2))
        elif a.cmd == "diag":
            print(json.dumps(ex.diag(), indent=2))
        elif a.cmd == "focus":
            print(json.dumps(ex.focus_window(), indent=2))
        elif a.cmd == "walk":
            scancode = int(a.args[0]) if a.args else 7
            hold = float(a.args[1]) if len(a.args) > 1 else 1.0
            print("down", ex.key(scancode, True))
            time.sleep(hold)
            print("up", ex.key(scancode, False))
        elif a.cmd == "key":
            print(ex.key(int(a.args[0]), a.args[1].lower() in ("1", "down", "true")))
        elif a.cmd == "text":
            print(ex.text(" ".join(a.args)))
        elif a.cmd == "mousemove":
            print(ex.mouse_move(float(a.args[0]), float(a.args[1]), False))
        elif a.cmd == "vmenable":
            print(ex.vm_enable(float(a.args[0]), float(a.args[1])))
        elif a.cmd == "vmmove":
            print(ex.vm_move(float(a.args[0]), float(a.args[1])))
        elif a.cmd == "vmdisable":
            print(ex.vm_disable())
        elif a.cmd == "sdlmouseraw":
            print(json.dumps(ex.sdl_mouse_raw(), indent=2))
        elif a.cmd == "vmstate":
            print(ex.vm_state())
        elif a.cmd == "mousestate":
            print(ex.mouse_state())
        elif a.cmd == "mousedown":
            print(ex.mouse_button(int(a.args[0]) if a.args else 1, True, 1))
        elif a.cmd == "mouseup":
            print(ex.mouse_button(int(a.args[0]) if a.args else 1, False, 1))
    finally:
        if messages:
            print("script messages:", json.dumps(messages)[:1000])
        script.unload()
        session.detach()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# SDL scancodes used by Factorio's default controls (US layout).
SCANCODES = {
    "a": 4, "b": 5, "c": 6, "d": 7, "e": 8, "f": 9, "g": 10, "h": 11,
    "i": 12, "j": 13, "k": 14, "l": 15, "m": 16, "n": 17, "o": 18, "p": 19,
    "q": 20, "r": 21, "s": 22, "t": 23, "u": 24, "v": 25, "w": 26, "x": 27,
    "y": 28, "z": 29, "1": 30, "2": 31, "3": 32, "4": 33, "5": 34, "6": 35,
    "7": 36, "8": 37, "9": 38, "0": 39, "enter": 40, "esc": 41, "escape": 41,
    "backspace": 42, "tab": 43, "space": 44, "minus": 45, "equals": 46,
    "leftbracket": 47, "rightbracket": 48, "backslash": 49, "semicolon": 51,
    "apostrophe": 52, "tilde": 53, "grave": 53, "comma": 54, "period": 55,
    "slash": 56, "capslock": 57, "f1": 58, "f2": 59, "f3": 60, "f4": 61,
    "f5": 62, "f6": 63, "f7": 64, "f8": 65, "f9": 66, "f10": 67, "f11": 68,
    "f12": 69, "insert": 73, "home": 74, "pageup": 75, "delete": 76, "end": 77,
    "pagedown": 78, "right": 79, "left": 80, "down": 81, "up": 82,
    "shift": 225, "lshift": 225, "rshift": 229, "ctrl": 224, "lctrl": 224,
    "rctrl": 228, "alt": 226, "lalt": 226, "ralt": 230,
}

DIRS = {
    "north": ["w"], "up": ["w"], "south": ["s"], "down": ["s"],
    "west": ["a"], "left": ["a"], "east": ["d"], "right": ["d"],
    "northwest": ["w", "a"], "nw": ["w", "a"],
    "northeast": ["w", "d"], "ne": ["w", "d"],
    "southwest": ["s", "a"], "sw": ["s", "a"],
    "southeast": ["s", "d"], "se": ["s", "d"],
}


def scancode_for(key: str) -> int:
    k = str(key).strip().lower()
    if k in SCANCODES:
        return SCANCODES[k]
    if k.startswith("0x"):
        return int(k, 16)
    return int(k)


class ClientInput:
    """Persistent SDL input channel for one Factorio client process.

    The virtual mouse state lives in this object's Frida script.  Keep the
    object alive for the whole bot session; do not create one per action,
    otherwise the game's real mouse-leave event can disable synthetic input.
    """

    def __init__(self, pid: int, timeout: float = 20.0):
        import frida
        self.frida = frida
        self.pid = pid
        self.timeout = timeout
        self.session = frida.attach(pid)
        self.script = self.session.create_script(JS)
        self.script.load()

    def info(self) -> dict:
        return self.script.exports_sync.sdl_info()

    def enable(self, x: float, y: float) -> dict:
        return self.script.exports_sync.vm_enable(float(x), float(y))

    def move(self, x: float, y: float) -> dict:
        return self.script.exports_sync.vm_move(float(x), float(y))

    def button(self, button: int = 1, down: bool = True, clicks: int = 1) -> dict:
        return self.script.exports_sync.mouse_button(int(button), bool(down), int(clicks))

    def click(self, x: float, y: float, button: int = 1, hold_ms: int = 0,
              double: bool = False) -> dict:
        out = self.move(x, y)
        out.update(self.button(button, True, 2 if double else 1))
        if hold_ms > 0:
            time.sleep(hold_ms / 1000.0)
        out.update(self.button(button, False, 2 if double else 1))
        if double:
            time.sleep(0.06)
            self.button(button, True, 2)
            time.sleep(0.04)
            self.button(button, False, 2)
        return out

    def key(self, scancode: int, down: bool) -> dict:
        return self.script.exports_sync.key(int(scancode), bool(down))

    def tap(self, scancode: int, hold_ms: int = 40) -> dict:
        self.key(scancode, True)
        time.sleep(hold_ms / 1000.0)
        return self.key(scancode, False)

    def text(self, text: str) -> dict:
        return self.script.exports_sync.text(str(text))

    def disable(self) -> dict:
        return self.script.exports_sync.vm_disable()

    def state(self) -> dict:
        return self.script.exports_sync.vm_state()

    def close(self) -> None:
        try:
            self.script.unload()
        except Exception:
            pass
        try:
            self.session.detach()
        except Exception:
            pass
