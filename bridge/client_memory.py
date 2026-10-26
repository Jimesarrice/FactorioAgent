#!/usr/bin/env python3
"""Read a running Factorio client's Lua state through a Frida-injected bridge.

This is a client-side, read-only memory/Lua probe.  It does not need an
AgentBridge scenario or RCON, and it does not need the game window to be
focused.  It attaches to factorio.exe, hooks lua_pcallk once to capture the
Lua state, and evaluates a Lua chunk on the game thread (inside an onLeave
hook) to read the local player position, inventory and nearby entities.

Version note: addresses below are public symbols from Factorio 2.1.23
(win64) and are resolved as module RVA, so they survive ASLR.  A game update
can move them; update the RVA table and re-run `probe`.

Safety: this module is intentionally read-only.  Writing game state from a
client can desync a multiplayer server; use normal input for actions.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Public symbol addresses (absolute in the 2.1.23 PE image with base
# 0x140000000).  RVA = address - 0x140000000.
BASE_140 = 0x140000000
RVA = {
    "luaL_loadstring": 0x1D0EDE0,
    "lua_pcallk": 0x1D0BF70,
    "lua_tolstring": 0x1D0A600,
    "lua_settop": 0x1D09D90,
    "lua_gettop": 0x1D09D70,
    "luaD_call": 0x1D137E0,
    "luaD_pcall": 0x1D138C0,
}

FRIDA_JS = r"""
const rva = %(rva)s;
const mod = Process.enumerateModules().find(m => m.name.toLowerCase() === 'factorio.exe');
if (!mod) throw new Error('factorio.exe module not found');
const base = mod.base;
const addr = {};
for (const k in rva) addr[k] = base.add(rva[k]);
const loadstring = new NativeFunction(addr.luaL_loadstring, 'int', ['pointer', 'pointer']);
const pcallk = new NativeFunction(addr.lua_pcallk, 'int',
    ['pointer', 'int', 'int', 'int', 'pointer', 'pointer']);
const tolstring = new NativeFunction(addr.lua_tolstring, 'pointer', ['pointer', 'int', 'pointer']);
const settop = new NativeFunction(addr.lua_settop, 'void', ['pointer', 'int']);
const gettop = new NativeFunction(addr.lua_gettop, 'int', ['pointer']);
const lenp = Memory.alloc(8);
let L = null;
let pending = null;
let inCall = false;
let lastError = null;
let lastStack = null;

function readTopString() {
    const p = tolstring(L, -1, lenp);
    if (p.isNull()) return '';
    const n = lenp.readU64().toNumber();
    try { return p.readUtf8String(n); } catch (e) { return '<binary>'; }
}

function pump() {
    if (!L || !pending || inCall) return;
    const req = pending;
    pending = null;
    inCall = true;
    let result;
    // Never wipe the caller's stack: the game may have live frames above us.
    // Push our chunk on top of the current top and restore it afterwards.
    let baseTop = -1;
    try {
        baseTop = gettop(L);
        const codeMem = Memory.allocUtf8String(req.code);
        const rc = loadstring(L, codeMem);
        if (rc !== 0) {
            result = { ok: false, error: 'luaL_loadstring=' + rc + ': ' + readTopString() };
            settop(L, baseTop);
        } else {
            const pr = pcallk(L, 0, 1, 0, ptr(0), ptr(0));
            if (pr !== 0) {
                result = { ok: false, error: 'lua_pcallk=' + pr + ': ' + readTopString() };
                settop(L, baseTop);
            } else {
                const s = readTopString();
                settop(L, baseTop);
                try { result = { ok: true, value: JSON.parse(s) }; }
                catch (e) { result = { ok: true, raw: s }; }
            }
        }
        lastStack = { baseTop, after: gettop(L) };
        lastError = result.ok ? null : result.error;
        if (req.timer) clearTimeout(req.timer);
        req.resolve(result);
    } catch (e) {
        try { if (baseTop >= 0) settop(L, baseTop); } catch (_) {}
        lastError = String(e);
        if (req.timer) clearTimeout(req.timer);
        req.reject(String(e));
    } finally {
        inCall = false;
    }
}

function capture(L0) {
    if (!L && L0 && !L0.isNull()) L = L0;
}

Interceptor.attach(addr.lua_pcallk, {
    onEnter(args) { capture(args[0]); },
    onLeave(retval) { pump(); }
});
Interceptor.attach(addr.luaD_call, {
    onEnter(args) { capture(args[0]); }
});

rpc.exports = {
    status() {
        return { attached: true, base: base.toString(), state: !!L,
                 pending: !!pending, lastError: lastError, lastStack: lastStack };
    },
    eval(code) {
        return new Promise((resolve, reject) => {
            const req = { code: String(code), resolve, reject, timer: null };
            req.timer = setTimeout(() => {
                if (pending === req) {
                    pending = null;
                    reject('timeout waiting for a game-thread Lua pcall (client not in game?)');
                }
            }, 15000);
            // Never execute Lua on the RPC thread; lua_pcallk's onLeave pumps it
            // on the game thread.
            pending = req;
        });
    }
};
""" % {"rva": json.dumps(RVA)}


class ClientMemory:
    def __init__(self, pid: int | None = None, process_name: str = "factorio.exe",
                 timeout: float = 20.0):
        import frida  # optional dependency; installed in the lab environment
        self.frida = frida
        self.timeout = timeout
        if pid is None:
            dev = frida.get_local_device()
            matches = [p for p in dev.enumerate_processes()
                       if p.name.lower() == process_name.lower()]
            if not matches:
                raise RuntimeError(f"no running {process_name}")
            pid = matches[0].pid
        self.pid = pid
        self.session = frida.attach(pid)
        self.script = self.session.create_script(FRIDA_JS)
        self.script.on("message", self._on_message)
        self.script.load()
        self._last_message = None

    def _on_message(self, message, data):
        # RPC results are returned by frida's exports API; keep script messages
        # for diagnostics only.
        self._last_message = message

    def status(self) -> dict:
        return self.script.exports_sync.status()

    def evaluate(self, code: str) -> dict:
        try:
            return self.script.exports_sync.eval(code)
        except Exception as e:
            raise RuntimeError(f"Frida Lua eval failed: {e}") from e

    def observe(self, name: str | None = None, radius: float = 32) -> dict:
        name_lua = json.dumps(name) if name else "nil"
        code = r"""
local p
if NAME ~= nil then p = game.get_player(NAME) end
if not p and game.player then p = game.player end
if not p then
  local candidates, names = {}, {}
  for _, q in pairs(game.connected_players or {}) do
    if q.character then candidates[#candidates+1] = q; names[#names+1] = q.name end
  end
  if #candidates == 1 then p = candidates[1]
  elseif #candidates > 1 then
    return { ok = false, error = 'multiple connected players; pass name', players = names }
  end
end
if not p then return { ok = false, error = 'no local player; pass name' } end
local c = p.character
if not c then return { ok = false, error = 'no character' } end
local items = {}
local inv = p.get_main_inventory()
if inv then
  for _, it in pairs(inv.get_contents()) do
    items[#items+1] = { name = it.name, count = it.count }
  end
end
local ents, resources = {}, {}
for _, e in pairs(c.surface.find_entities_filtered({ position = c.position, radius = RADIUS })) do
  if e.type == 'resource' then
    resources[#resources+1] = { name = e.name, amount = e.amount,
      x = e.position.x, y = e.position.y }
  elseif e.type ~= 'character' then
    ents[#ents+1] = { name = e.name, type = e.type,
      x = e.position.x, y = e.position.y, unit_number = e.unit_number,
      status = e.status }
  end
end
local selected = nil
local ok_sel, sel = pcall(function() return p.selected end)
if ok_sel and sel and sel.valid then
  selected = { name = sel.name, type = sel.type,
    x = sel.position.x, y = sel.position.y, unit_number = sel.unit_number }
end
local research = nil
local ok_res, cur = pcall(function() return p.force.current_research end)
if ok_res then
  research = { current = cur and cur.name or nil,
    progress = p.force.research_progress }
end
return {
  ok = true, tick = game.tick, surface = c.surface.name,
  player = p.name, position = { x = c.position.x, y = c.position.y },
  health = c.health, inventory = items, resources = resources,
  entities = ents, selected = selected, research = research
}
""".replace("NAME", name_lua).replace("RADIUS", str(float(radius)))
        return self.evaluate("return helpers.table_to_json((function() " + code + " end)())")

    def inventory(self, name: str | None = None) -> dict:
        name_lua = json.dumps(name) if name else "nil"
        code = r"""
local p
if NAME ~= nil then p = game.get_player(NAME) end
if not p and game.player then p = game.player end
if not p then
  local candidates, names = {}, {}
  for _, q in pairs(game.connected_players or {}) do
    if q.character then candidates[#candidates+1] = q; names[#names+1] = q.name end
  end
  if #candidates == 1 then p = candidates[1]
  elseif #candidates > 1 then
    return { ok = false, error = 'multiple connected players; pass name', players = names }
  end
end
if not p then return { ok = false, error = 'no local player; pass name' } end
local items = {}
local inv = p.get_main_inventory()
if inv then for _, it in pairs(inv.get_contents()) do items[#items+1] = { name = it.name, count = it.count } end end
return { ok = true, player = p.name, inventory = items }
""".replace("NAME", name_lua)
        return self.evaluate("return helpers.table_to_json((function() " + code + " end)())")

    def close(self) -> None:
        try:
            self.script.unload()
        except Exception:
            pass
        try:
            self.session.detach()
        except Exception:
            pass


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Read Factorio client state via Frida (read-only)")
    ap.add_argument("--pid", type=int)
    ap.add_argument("--name", help="bot player name (e.g. LLM-Bot-11)")
    ap.add_argument("--radius", type=float, default=32)
    ap.add_argument("--timeout", type=float, default=20)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("probe")
    sub.add_parser("status")
    sub.add_parser("observe")
    sub.add_parser("inventory")
    p = sub.add_parser("lua"); p.add_argument("code")
    a = ap.parse_args(argv)
    try:
        cm = ClientMemory(a.pid, timeout=a.timeout)
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 1
    try:
        if a.cmd == "status":
            result = cm.status()
        elif a.cmd == "probe":
            result = cm.evaluate("return helpers.table_to_json({ok=true, tick=game.tick, player=(game.player and game.player.name) or nil})")
        elif a.cmd == "observe":
            result = cm.observe(a.name, a.radius)
        elif a.cmd == "inventory":
            result = cm.inventory(a.name)
        elif a.cmd == "lua":
            result = cm.evaluate(a.code)
        else:
            result = {"ok": False, "error": "unknown command"}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok", True) else 1
    finally:
        cm.close()


if __name__ == "__main__":
    raise SystemExit(main())
