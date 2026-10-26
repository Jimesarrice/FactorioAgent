#!/usr/bin/env python3
"""High-level background actions for a running Factorio client.

Combines the persistent SDL input channel with read-only Lua state to perform
normal-player actions without window focus:

* walk to a world position;
* mine the nearest resource (right mouse held; move the cursor off all
  entities to stop, the reliable background stop on this build);
* pick an item from the character inventory through the GUI;
* build an item on the ground (left click);
* open an entity GUI and close it.

All actions are normal client input.  No Lua state writes, no entity edits and
no network packet forgery.  The server remains authoritative.

Known limits:
- After a background mining hold, the client keeps the right button in its
  input state until a real mouse-up; use a blank tile to stop mining.  Build
  mining drills on ore *before* mining, because moving over ore with the held
  right button starts mining again.
- The inventory slot geometry below was measured on a 3440x1440 client
  (UI scale 1.25).  Override origin/slot/columns for other resolutions.
- Opening an entity GUI cannot be verified through the safe Lua state (the
  `opened` API can throw on a client); use a screenshot or the UI.
"""
from __future__ import annotations

import math
import time

from .client_input import ClientInput, SCANCODES
from .client_memory import ClientMemory


class ClientActions:
    def __init__(self, pid: int, name: str | None = None,
                 inventory_origin: tuple[float, float] = (1228.0, 524.0),
                 inventory_slot: float = 44.0, inventory_columns: int = 10,
                 px_per_tile_zoom1: float = 42.6666667):
        self.pid = pid
        self.name = name
        self.input = ClientInput(pid)
        self.memory = ClientMemory(pid)
        self.inventory_origin = inventory_origin
        self.inventory_slot = inventory_slot
        self.inventory_columns = inventory_columns
        self.px_per_tile_zoom1 = px_per_tile_zoom1

    # ------------------------------------------------------------------ state
    def controller_type(self) -> int | None:
        """Safe remote-view probe; does not touch p.character."""
        name_lua = repr(self.name) if self.name else "nil"
        code = r"""
local p
if NAME ~= nil then p=game.get_player(NAME) end
if not p and game.player then p=game.player end
if not p then
  local cs={}
  for _,q in pairs(game.connected_players or {}) do if q.character then cs[#cs+1]=q end end
  if #cs==1 then p=cs[1] end
end
if not p then return helpers.table_to_json({ok=false,error='no local player'}) end
return helpers.table_to_json({ok=true, controller=p.controller_type, player=p.name})
""".replace("NAME", name_lua)
        raw = self.memory.evaluate(code)
        val = raw.get("value") if isinstance(raw, dict) and raw.get("ok") else raw
        if not isinstance(val, dict) or not val.get("ok"):
            raise RuntimeError(f"controller probe failed: {val}")
        return val.get("controller")

    def _ensure_character(self) -> None:
        ct = self.controller_type()
        for _ in range(3):
            if ct == 1:
                return
            self.input.tap(SCANCODES["m"], 70)
            time.sleep(0.7)
            ct = self.controller_type()
        if ct != 1:
            raise RuntimeError(f"not in character controller (controller={ct}); press M to leave remote view")

    def state(self) -> dict:
        self._ensure_character()
        name_lua = repr(self.name) if self.name else "nil"
        code = r"""
local p
if NAME ~= nil then p=game.get_player(NAME) end
if not p and game.player then p=game.player end
if not p then
  local cs={}
  for _,q in pairs(game.connected_players or {}) do if q.character then cs[#cs+1]=q end end
  if #cs==1 then p=cs[1] end
end
if not p or not p.character then return helpers.table_to_json({ok=false,error='no local player/character'}) end
local c=p.character
local s=p.selected
local cur=p.cursor_stack
local inv=p.get_main_inventory()
local items={}
if inv then
  for _,it in pairs(inv.get_contents()) do
    items[#items+1]={name=it.name,count=it.count}
  end
end
return helpers.table_to_json({
  ok=true, tick=game.tick, player=p.name, controller=p.controller_type,
  zoom=p.zoom, pos={x=c.position.x,y=c.position.y},
  selected=(s and s.valid) and s.name or nil,
  mining=c.mining_state.mining,
  cursor=cur and cur.valid_for_read and cur.name or nil,
  inventory=items, opened_self=p.opened_self
})
""".replace("NAME", name_lua)
        raw = self.memory.evaluate(code)
        val = raw.get("value") if isinstance(raw, dict) and raw.get("ok") else raw
        if not isinstance(val, dict) or not val.get("ok"):
            raise RuntimeError(f"state failed: {val}")
        try:
            val["virtual"] = self.input.state()
        except Exception:
            val["virtual"] = None
        return val

    def inventory_count(self, item: str) -> int:
        return sum(int(i.get("count", 0)) for i in self.state().get("inventory", [])
                   if i.get("name") == item)

    def screen(self) -> tuple[float, float, float]:
        info = self.input.info()
        win = (info.get("windows") or [{}])[0]
        w = float(win.get("w") or 3440)
        h = float(win.get("h") or 1440)
        st = self.state()
        scale = self.px_per_tile_zoom1 * float(st.get("zoom") or 1.0)
        return w / 2.0, h / 2.0, scale

    # ------------------------------------------------------------- UI/character
    def ensure_character(self) -> dict:
        st = self.state()
        if st.get("opened_self"):
            self.input.tap(SCANCODES["e"], 60)
            time.sleep(0.4)
            st = self.state()
        return st

    def close_ui(self) -> dict:
        st = self.state()
        if st.get("opened_self"):
            self.input.tap(SCANCODES["e"], 60)
            time.sleep(0.4)
        return self.state()

    # ---------------------------------------------------------------- geometry
    def _screen_for(self, st: dict, x: float, y: float) -> tuple[float, float, float]:
        info = self.input.info()
        win = (info.get("windows") or [{}])[0]
        w = float(win.get("w") or 3440)
        h = float(win.get("h") or 1440)
        scale = self.px_per_tile_zoom1 * float(st.get("zoom") or 1.0)
        return w / 2.0 + (x - st["pos"]["x"]) * scale, h / 2.0 + (y - st["pos"]["y"]) * scale, scale

    def aim_world(self, x: float, y: float) -> dict:
        st = self.state()
        if st.get("controller") != 1:
            st = self.ensure_character()
        sx, sy, _ = self._screen_for(st, x, y)
        self.input.move(sx, sy)
        time.sleep(0.35)
        return self.state()

    def aim_blank(self) -> dict:
        st = self.state()
        px, py = st["pos"]["x"], st["pos"]["y"]
        for radius in (5, 7, 9, 12, 15, 20):
            for dx, dy in ((radius, 0), (-radius, 0), (0, radius), (0, -radius),
                           (radius, radius), (-radius, radius), (radius, -radius), (-radius, -radius)):
                wx, wy = px + dx, py + dy
                q = self.memory.evaluate(
                    "local p=game.get_player('LLM-Bot'); local c=p.character; "
                    f"local e=c.surface.find_entities_filtered({{position={{x={wx},y={wy}}},radius=1}}); "
                    "return helpers.table_to_json({ok=true,n=#e})")
                n = (q.get("value") or {}).get("n") if isinstance(q, dict) else None
                if not n:
                    return self.aim_world(wx, wy)
        raise RuntimeError("no blank tile found around player")

    # ------------------------------------------------------------------ mining
    def _resource_item(self, resource: str) -> str:
        return {"tree": "wood", "simple-entity": "stone"}.get(resource, resource)

    def mine_nearest(self, resource: str = "iron-ore", count: int = 1,
                     radius: float = 16, timeout: float = 20.0) -> dict:
        self.ensure_character()
        st = self.state()
        if st.get("cursor"):
            self.input.tap(SCANCODES["q"], 50)
            time.sleep(0.25)
            st = self.state()
        item = self._resource_item(resource)
        start = self.inventory_count(item)
        deadline = time.time() + timeout
        target = None
        while time.time() < deadline:
            st = self.state()
            px, py = st["pos"]["x"], st["pos"]["y"]
            q = self.memory.evaluate(
                "local p=game.get_player('LLM-Bot'); local c=p.character; local t={}; "
                f"for _,e in pairs(c.surface.find_entities_filtered({{position=c.position,radius={radius},type='resource'}})) do "
                f"if e.name=={resource!r} then t[#t+1]={{x=e.position.x,y=e.position.y,amount=e.amount}} end end; "
                "return helpers.table_to_json({ok=true,res=t})")
            res = (q.get("value") or {}).get("res") or []
            res = [r for r in res
                   if math.hypot(r["x"] - px, r["y"] - py) >= 0.7]
            res.sort(key=lambda r: (r["x"] - px) ** 2 + (r["y"] - py) ** 2)
            close = [r for r in res if math.hypot(r["x"] - px, r["y"] - py) <= 2.3]
            target = (close or res or [None])[0]
            if target is None:
                raise RuntimeError(f"no {resource} within {radius} tiles")
            d = math.hypot(target["x"] - px, target["y"] - py)
            if d <= 2.3:
                break
            self.walk_to(target["x"], target["y"], tolerance=1.8, timeout=12)
        if target is None:
            raise RuntimeError("no mining target")
        aimed = False
        for dx, dy in ((0, 0), (0.4, 0), (-0.4, 0), (0, 0.4), (0, -0.4)):
            st = self.aim_world(target["x"] + dx, target["y"] + dy)
            if st.get("selected") == resource:
                aimed = True
                break
        if not aimed:
            raise RuntimeError(f"cursor did not select {resource} at {target}")
        self.input.button(3, True)
        while time.time() < deadline:
            time.sleep(0.35)
            got = self.inventory_count(item) - start
            st = self.state()
            if got >= count:
                break
            if st.get("mining") is False and st.get("selected") != resource:
                break
        try:
            self.aim_blank()
        finally:
            self.input.button(3, False)
            self.input.release_all()
        time.sleep(0.4)
        st = self.state()
        return {"ok": True, "item": item, "mined": self.inventory_count(item) - start,
                "mining": st.get("mining"), "target": target, "state": st}

    def stop_mining(self) -> dict:
        self.aim_blank()
        self.input.release_all()
        time.sleep(0.3)
        return self.state()

    # ----------------------------------------------------------------- walking
    def walk_to(self, x: float, y: float, tolerance: float = 0.8,
                timeout: float = 30.0) -> dict:
        deadline = time.time() + timeout
        blocked = 0
        while time.time() < deadline:
            st = self.state()
            px, py = st["pos"]["x"], st["pos"]["y"]
            dx, dy = x - px, y - py
            if math.hypot(dx, dy) <= tolerance:
                return st
            keys = []
            if abs(dx) > tolerance:
                keys.append(SCANCODES["d"] if dx > 0 else SCANCODES["a"])
            if abs(dy) > tolerance:
                keys.append(SCANCODES["s"] if dy > 0 else SCANCODES["w"])
            for k in keys:
                self.input.key(k, True)
            time.sleep(min(0.25, max(0.12, math.hypot(dx, dy) / 30.0)))
            for k in keys:
                self.input.key(k, False)
            time.sleep(0.15)
            st2 = self.state()
            moved = math.hypot(st2["pos"]["x"] - px, st2["pos"]["y"] - py)
            if moved < 0.08:
                blocked += 1
                if abs(dx) > abs(dy):
                    detour = SCANCODES["s"] if dy < 0 else SCANCODES["w"]
                else:
                    detour = SCANCODES["d"] if dx < 0 else SCANCODES["a"]
                self.input.key(detour, True)
                time.sleep(0.5)
                self.input.key(detour, False)
                time.sleep(0.2)
                if blocked >= 5:
                    raise RuntimeError(f"walk_to blocked near {st2['pos']}")
        raise RuntimeError(f"walk_to timeout to ({x},{y})")

    # -------------------------------------------------------------------- GUI
    def _slot_screen(self, index: int) -> tuple[float, float]:
        i = index - 1
        col = i % self.inventory_columns
        row = i // self.inventory_columns
        return (self.inventory_origin[0] + col * self.inventory_slot,
                self.inventory_origin[1] + row * self.inventory_slot)

    def pick_item(self, item: str) -> dict:
        st = self.ensure_character()
        if st.get("cursor") == item:
            return st
        if st.get("cursor"):
            self.input.tap(SCANCODES["q"], 50)
            time.sleep(0.25)
            st = self.state()
            if st.get("cursor"):
                raise RuntimeError(f"cursor busy with {st.get('cursor')}")
        if not st.get("opened_self"):
            self.input.tap(SCANCODES["e"], 60)
            time.sleep(0.5)
            st = self.state()
            if not st.get("opened_self"):
                raise RuntimeError("could not open character inventory")
        picked = False
        for index in range(1, 31):
            sx, sy = self._slot_screen(index)
            self.input.move(sx, sy)
            time.sleep(0.1)
            self.input.button(1, True)
            time.sleep(0.08)
            self.input.button(1, False)
            time.sleep(0.22)
            cur = self.state().get("cursor")
            if cur == item:
                picked = True
                break
            if cur:
                self.input.button(1, True)
                time.sleep(0.08)
                self.input.button(1, False)
                time.sleep(0.18)
                if self.state().get("cursor"):
                    raise RuntimeError(f"cannot return item {cur} to slot {index}")
        if not picked:
            self.close_ui()
            raise RuntimeError(f"item {item!r} not found in first 30 inventory slots")
        self.aim_blank()
        self.input.tap(SCANCODES["e"], 60)
        time.sleep(0.45)
        st = self.state()
        if st.get("cursor") != item:
            raise RuntimeError(f"lost cursor item after closing inventory (cursor={st.get('cursor')})")
        return st

    # ------------------------------------------------------------------ build
    def build_item(self, item: str, x: float, y: float,
                   on_ore: bool = False, direction: int | None = None) -> dict:
        st = self.ensure_character()
        if st.get("cursor") != item:
            st = self.pick_item(item)
        if st.get("cursor") != item:
            raise RuntimeError(f"cursor does not hold {item}")
        px, py = st["pos"]["x"], st["pos"]["y"]
        spots = []
        for r in range(0, 6):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) != r:
                        continue
                    wx, wy = x + dx * 0.5, y + dy * 0.5
                    if math.hypot(wx - px, wy - py) > 9.5:
                        continue
                    q = self.memory.evaluate(
                        "local p=game.get_player('LLM-Bot'); local c=p.character; "
                        f"local ok,r=pcall(function() return c.surface.can_place_entity{{name={item!r},position={{x={wx},y={wy}}},force=p.force}} end); "
                        f"local ore=#c.surface.find_entities_filtered({{position={{x={wx},y={wy}}},radius=1.6,type='resource'}})>0; "
                        "return helpers.table_to_json({ok=true,can=ok and r or false,ore=ore})")
                    v = q.get("value") or {}
                    if v.get("can") and (v.get("ore") if on_ore else not v.get("ore")):
                        spots.append((wx, wy, v.get("ore")))
                        if len(spots) >= 20:
                            break
                if len(spots) >= 20:
                    break
            if len(spots) >= 20:
                break
        if not spots:
            raise RuntimeError(f"no valid placement for {item} near ({x},{y})")
        spots.sort(key=lambda s: (s[0] - x) ** 2 + (s[1] - y) ** 2)
        wx, wy, ore = spots[0]
        aimed = self.aim_world(wx, wy)
        if aimed.get("mining"):
            self.aim_blank()
            self.input.release_all()
            raise RuntimeError("right mouse is held and started mining; build drills before mining")
        if direction is not None:
            self.input.tap(SCANCODES["r"], 50)
            time.sleep(0.2)
        self.input.button(1, True)
        time.sleep(0.18)
        self.input.button(1, False)
        time.sleep(0.8)
        st = self.state()
        q = self.memory.evaluate(
            "local p=game.get_player('LLM-Bot'); local c=p.character; "
            f"local e=c.surface.find_entities_filtered({{name={item!r},position={{x={wx},y={wy}}},radius=2.5}}); "
            "return helpers.table_to_json({ok=true,n=#e,pos=(#e>0) and {x=e[1].position.x,y=e[1].position.y} or nil})")
        v = q.get("value") or {}
        return {"ok": bool(v.get("n")), "item": item,
                "placement": {"x": wx, "y": wy, "ore": ore},
                "focused": aimed, "state": st, "found": v.get("n")}

    # ----------------------------------------------------------------- detect
    def open_entity(self, x: float, y: float) -> dict:
        st = self.ensure_character()
        if st.get("cursor"):
            self.input.tap(SCANCODES["q"], 50)
            time.sleep(0.25)
        st = self.aim_world(x, y)
        self.input.button(1, True)
        time.sleep(0.15)
        self.input.button(1, False)
        time.sleep(0.8)
        return self.state()

    def close(self) -> None:
        try:
            self.input.disable()
        except Exception:
            pass
        try:
            self.input.close()
        except Exception:
            pass
        try:
            self.memory.close()
        except Exception:
            pass
