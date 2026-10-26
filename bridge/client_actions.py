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
    # Entity GUI layouts measured on the 3440x1440 client (UI scale 1.25):
    # "char" is slot 1 of the character panel shown next to the entity window,
    # the other keys are the entity's own slots.
    ENTITY_GUI = {
        "stone-furnace": {"char": (1223.0, 508.0), "input": (1769.0, 765.0),
                          "output": (2210.0, 765.0), "fuel": (1766.0, 838.0)},
        "burner-mining-drill": {"char": (1223.0, 518.0),
                                "fuel": (1767.0, 782.0)},
        "wooden-chest": {"char": (1223.0, 508.0), "slot1": (1764.0, 715.0)},
    }

    def __init__(self, pid: int, name: str | None = None,
                 inventory_origin: tuple[float, float] = (1223.0, 523.0),
                 inventory_slot: float = 50.0, inventory_columns: int = 10,
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

    def close_all_ui(self) -> dict:
        """Close entity GUIs and the character screen.

        E closes the topmost window, or opens the character screen when none
        is open.  opened_self only reports the character screen, so a single E
        is probed: if it opened the inventory instead of closing an entity GUI,
        the inventory is closed again.
        """
        st = self.state()
        if st.get("opened_self"):
            self.input.tap(SCANCODES["e"], 60)
            time.sleep(0.45)
            return self.state()
        self.input.tap(SCANCODES["e"], 60)
        time.sleep(0.5)
        nxt = self.state()
        if nxt.get("opened_self"):
            # nothing was open: E opened the character screen, close it again
            self.input.tap(SCANCODES["e"], 60)
            time.sleep(0.45)
            return self.state()
        return nxt

    # --------------------------------------------------------------- crafting
    # Character-screen geometry, 3440x1440 at UI scale 1.25.
    CRAFT_SEARCH = (2199.0, 415.0)   # magnifier button in the title bar
    CRAFT_CLOSE = (2241.0, 414.0)    # X button of the character screen
    CRAFT_FIRST = (1758.0, 565.0)    # first recipe cell of the filtered list

    def open_character_screen(self) -> dict:
        st = self.state()
        if not st.get("opened_self"):
            self.input.tap(SCANCODES["e"], 60)
            time.sleep(0.6)
            st = self.state()
        if not st.get("opened_self"):
            raise RuntimeError("could not open the character screen")
        return st

    def close_character_screen(self) -> dict:
        st = self.state()
        if st.get("opened_self"):
            self.input.click(self.CRAFT_CLOSE[0], self.CRAFT_CLOSE[1], 1, 30)
            time.sleep(0.6)
        return self.state()

    def craft(self, query: str, count: int = 1, timeout: float = 20.0) -> dict:
        """Hand-craft via the searchable crafting list (normal GUI input).

        ``query`` is the English recipe text shown in the search (e.g.
        "wooden chest").  One click on the first result queues one craft;
        shift-click would queue five but the plain click keeps control simple.
        """
        self._ensure_character()
        # Reopen the screen so the crafting search never carries a stale
        # query or an already-open search field from a previous call.
        self.close_character_screen()
        self.open_character_screen()
        ci = self.input
        try:
            ci.key(SCANCODES["ctrl"], True)
            ci.tap(SCANCODES["f"], 40)
            ci.key(SCANCODES["ctrl"], False)
            time.sleep(0.45)
            ci.key(SCANCODES["ctrl"], True)
            ci.tap(SCANCODES["a"], 40)
            ci.key(SCANCODES["ctrl"], False)
            time.sleep(0.15)
            ci.text(query)
            time.sleep(0.55)
            before = {i["name"]: int(i["count"]) for i in self.state().get("inventory", [])}
            for _ in range(max(1, int(count))):
                ci.click(self.CRAFT_FIRST[0], self.CRAFT_FIRST[1], 1, 30)
                time.sleep(0.22)
            deadline = time.time() + timeout
            gained: dict[str, int] = {}
            st = self.state()
            while time.time() < deadline:
                st = self.state()
                inv = {i["name"]: int(i["count"]) for i in st.get("inventory", [])}
                gained = {k: v - before.get(k, 0) for k, v in inv.items()
                          if v > before.get(k, 0)}
                if gained:
                    break
                time.sleep(0.3)
        finally:
            self.close_character_screen()
        return {"ok": bool(gained), "query": query, "requested": count,
                "gained": gained, "inventory": self.state().get("inventory")}

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

    def _find_entities(self, radius: float, name: str | None = None,
                       etype: str | None = None) -> list[dict]:
        parts = ["position=c.position", f"radius={radius}"]
        if name:
            parts.append(f"name={name!r}")
        if etype:
            parts.append(f"type={etype!r}")
        code = ("local p=game.get_player('LLM-Bot'); local c=p.character; local t={}; "
                "for _,e in pairs(c.surface.find_entities_filtered{" + ",".join(parts) + "}) do "
                "t[#t+1]={name=e.name,type=e.type,x=e.position.x,y=e.position.y} end; "
                "return helpers.table_to_json({ok=true,es=t})")
        q = self.memory.evaluate(code)
        return (q.get("value") or {}).get("es") or []

    def _entity_exists_at(self, x: float, y: float, name: str | None = None,
                          etype: str | None = None) -> bool:
        parts = [f"position={{x={x},y={y}}}", "radius=0.9"]
        if name:
            parts.append(f"name={name!r}")
        if etype:
            parts.append(f"type={etype!r}")
        code = ("local p=game.get_player('LLM-Bot'); local c=p.character; "
                "local e=c.surface.find_entities_filtered{" + ",".join(parts) + "}; "
                "return helpers.table_to_json({ok=true,n=#e})")
        q = self.memory.evaluate(code)
        return bool((q.get("value") or {}).get("n"))

    def mine_entity(self, name: str | None = None, etype: str | None = None,
                    item: str | None = None, radius: float = 64,
                    timeout: float = 90.0) -> dict:
        """Walk to and mine the nearest tree/simple-entity by right-holding.

        Stops by moving to a blank tile (reliable background stop) and emits
        an atomic right-click pair so the client's held-button state clears.
        """
        self.ensure_character()
        self.close_all_ui()
        st = self.state()
        if st.get("cursor"):
            self.input.tap(SCANCODES["q"], 50)
            time.sleep(0.25)
            st = self.state()
        item = item or self._resource_item(name or etype or "")
        start = self.inventory_count(item) if item else 0
        deadline = time.time() + timeout
        target = None
        while time.time() < deadline:
            st = self.state()
            px, py = st["pos"]["x"], st["pos"]["y"]
            es = [e for e in self._find_entities(radius, name, etype)
                  if math.hypot(e["x"] - px, e["y"] - py) > 0.6]
            es.sort(key=lambda e: (e["x"] - px) ** 2 + (e["y"] - py) ** 2)
            close = [e for e in es if math.hypot(e["x"] - px, e["y"] - py) <= 2.2]
            target = (close or es or [None])[0]
            if target is None:
                raise RuntimeError(f"no entity {name or etype} within {radius} tiles")
            if math.hypot(target["x"] - px, target["y"] - py) <= 2.2:
                break
            self.walk_to(target["x"], target["y"], tolerance=1.7, timeout=25)
        if target is None:
            raise RuntimeError("no mining target")
        aimed = False
        for dx, dy in ((0, 0), (0.5, 0), (-0.5, 0), (0, 0.5), (0, -0.5),
                       (0.5, 0.5), (-0.5, 0.5), (0.5, -0.5), (-0.5, -0.5)):
            st = self.aim_world(target["x"] + dx, target["y"] + dy)
            sel = st.get("selected")
            if sel == target["name"]:
                aimed = True
                break
        if not aimed:
            # selected may stay nil for some entity types; aim directly anyway
            self.aim_world(target["x"], target["y"])
        self.input.button(3, True)
        while time.time() < deadline:
            time.sleep(0.3)
            if not self._entity_exists_at(target["x"], target["y"], target["name"]):
                break
            got = self.inventory_count(item) - start if item else 0
            if item and got >= 1:
                break
        try:
            self.aim_blank()
        finally:
            self.input.click_pair(3, 0)
            self.input.release_all()
        time.sleep(0.4)
        st = self.state()
        return {"ok": True, "target": target,
                "gained": (self.inventory_count(item) - start) if item else None,
                "inventory": st.get("inventory"), "mining": st.get("mining")}

    def mine_nearest(self, resource: str = "iron-ore", count: int = 1,
                     radius: float = 16, timeout: float = 20.0) -> dict:
        self.ensure_character()
        self.close_all_ui()
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
        # Re-pick a target that is not underfoot: standing on the ore tile
        # makes it impossible to hover (and the character covers it).
        st = self.state()
        px, py = st["pos"]["x"], st["pos"]["y"]
        def ring(lo, hi):
            out = [r for r in res
                   if lo <= math.hypot(r["x"] - px, r["y"] - py) <= hi]
            out.sort(key=lambda r: (r["x"] - px) ** 2 + (r["y"] - py) ** 2)
            return out
        near = ring(1.5, 2.4) or ring(0.9, 2.4)
        if near:
            target = near[0]
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
            self.input.click_pair(3, 0)
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
    def _walk_grid(self, radius: int = 24) -> dict | None:
        code = (
            "local p=game.get_player('LLM-Bot'); local c=p.character; "
            f"local R={radius}; local cx,cy=math.floor(c.position.x),math.floor(c.position.y); "
            "local rows={}; "
            "for dy=-R,R do local row={}; "
            "for dx=-R,R do local t=c.surface.get_tile(cx+dx,cy+dy); "
            "row[#row+1]=(t and t.collides_with('player')) and '1' or '0' end; "
            "rows[#rows+1]=table.concat(row) end; "
            "return helpers.table_to_json({ok=true,cx=cx,cy=cy,r=R,rows=rows})")
        q = self.memory.evaluate(code)
        return q.get("value") if isinstance(q, dict) else q

    def _plan_path(self, x: float, y: float, radius: int = 24):
        """BFS over the client's tile collision grid (read-only Lua)."""
        from collections import deque
        g = self._walk_grid(radius)
        if not g or not g.get("ok"):
            return None
        cx, cy, r = int(g["cx"]), int(g["cy"]), int(g["r"])
        rows = g["rows"]

        def blocked(ix: int, iy: int) -> bool:
            dx, dy = ix - cx, iy - cy
            if abs(dx) > r or abs(dy) > r:
                return True
            return rows[dy + r][dx + r] == "1"

        start = (cx, cy)
        goal = (math.floor(x), math.floor(y))
        prev = {start: None}
        queue = deque([start])
        best, best_d = start, (start[0] - goal[0]) ** 2 + (start[1] - goal[1]) ** 2
        while queue:
            cur = queue.popleft()
            d = (cur[0] - goal[0]) ** 2 + (cur[1] - goal[1]) ** 2
            if d < best_d:
                best, best_d = cur, d
            if cur == goal:
                break
            for ddx, ddy in ((1, 0), (-1, 0), (0, 1), (0, -1),
                             (1, 1), (1, -1), (-1, 1), (-1, -1)):
                nxt = (cur[0] + ddx, cur[1] + ddy)
                if nxt in prev or blocked(*nxt):
                    continue
                if ddx and ddy and (blocked(cur[0] + ddx, cur[1]) or
                                    blocked(cur[0], cur[1] + ddy)):
                    continue
                prev[nxt] = cur
                queue.append(nxt)
        node = goal if goal in prev else best
        if node not in prev:
            return None
        path = []
        while node is not None:
            path.append(node)
            node = prev[node]
        path.reverse()
        if len(path) < 2:
            return [(x, y)]
        points = [(p[0] + 0.5, p[1] + 0.5) for p in path[1:]]
        if node == goal:
            points[-1] = (x, y)
        return points

    def _walk_step(self, wx: float, wy: float, deadline: float) -> float:
        px = py = None
        st = self.state()
        px, py = st["pos"]["x"], st["pos"]["y"]
        dx, dy = wx - px, wy - py
        dist = math.hypot(dx, dy)
        keys = []
        if abs(dx) > 0.25:
            keys.append(SCANCODES["d"] if dx > 0 else SCANCODES["a"])
        if abs(dy) > 0.25:
            keys.append(SCANCODES["s"] if dy > 0 else SCANCODES["w"])
        if not keys:
            return dist
        hold = min(0.45, max(0.12, dist / 3.2))
        for k in keys:
            self.input.key(k, True)
        time.sleep(hold)
        for k in keys:
            self.input.key(k, False)
        time.sleep(0.1)
        st2 = self.state()
        return math.hypot(st2["pos"]["x"] - px, st2["pos"]["y"] - py)

    def walk_to(self, x: float, y: float, tolerance: float = 0.8,
                timeout: float = 60.0) -> dict:
        deadline = time.time() + timeout
        stuck_runs = 0
        while time.time() < deadline:
            st = self.state()
            px, py = st["pos"]["x"], st["pos"]["y"]
            if math.hypot(x - px, y - py) <= tolerance:
                return st
            try:
                path = self._plan_path(x, y)
            except Exception:
                path = None
            if path:
                moved_total = 0.0
                for wx, wy in path[:14]:
                    if time.time() > deadline:
                        break
                    cur = self.state()
                    if math.hypot(wx - cur["pos"]["x"], wy - cur["pos"]["y"]) <= 0.35:
                        continue
                    moved = self._walk_step(wx, wy, deadline)
                    moved_total += moved
                    if moved < 0.05:
                        break
                if moved_total < 0.15:
                    stuck_runs += 1
                    if stuck_runs >= 4:
                        raise RuntimeError(f"walk_to blocked near ({px:.1f},{py:.1f})")
                else:
                    stuck_runs = 0
            else:
                moved = self._walk_step(x, y, deadline)
                if moved < 0.05:
                    stuck_runs += 1
                    if stuck_runs >= 4:
                        raise RuntimeError(f"walk_to blocked near ({px:.1f},{py:.1f})")
                else:
                    stuck_runs = 0
        st = self.state()
        px, py = st["pos"]["x"], st["pos"]["y"]
        if math.hypot(x - px, y - py) > max(tolerance, 1.5):
            raise RuntimeError(f"walk_to timeout to ({x},{y}) at ({px:.1f},{py:.1f})")
        return st

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
            self.input.click(sx, sy, 1, 30)
            time.sleep(0.3)
            cur = self.state().get("cursor")
            if cur == item:
                picked = True
                break
            if cur:
                self.input.click(sx, sy, 1, 30)
                time.sleep(0.25)
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
        self.close_all_ui()
        st = self.state()
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
        self.input.click_pair(1, 40)
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

    # --------------------------------------------------------- fast transfer
    def mod_click(self, x: float, y: float, mod: str = "ctrl",
                  button: int = 1) -> dict:
        """Click with Ctrl held (Factorio's fast-transfer modifier)."""
        self.input.move(x, y)
        time.sleep(0.15)
        self.input.key(SCANCODES[mod], True)
        time.sleep(0.08)
        self.input.click_pair(button, 30)
        time.sleep(0.15)
        self.input.key(SCANCODES[mod], False)
        time.sleep(0.35)
        return self.state()

    def _pick_from_open_gui(self, item: str, origin: tuple[float, float]) -> dict:
        """Pick a stack from the character panel docked to an entity window."""
        st = self.state()
        if st.get("cursor"):
            raise RuntimeError(f"cursor busy with {st.get('cursor')}")
        for index in range(1, 31):
            col = (index - 1) % self.inventory_columns
            row = (index - 1) // self.inventory_columns
            sx = origin[0] + col * self.inventory_slot
            sy = origin[1] + row * self.inventory_slot
            self.input.click(sx, sy, 1, 30)
            time.sleep(0.28)
            cur = self.state().get("cursor")
            if cur == item:
                return self.state()
            if cur:
                self.input.click(sx, sy, 1, 30)
                time.sleep(0.25)
                if self.state().get("cursor"):
                    raise RuntimeError(f"cannot return {cur} to slot {index}")
        raise RuntimeError(f"item {item!r} not found in the open inventory panel")

    def entity_insert(self, x: float, y: float, entity_name: str,
                      item: str, slot: str = "input") -> dict:
        """Open an entity and move one player stack into one of its slots."""
        geo = self.ENTITY_GUI.get(entity_name)
        if not geo:
            raise RuntimeError(f"no GUI layout known for {entity_name}")
        st = self.open_entity(x, y)
        if st.get("cursor"):
            self.input.tap(SCANCODES["q"], 50)
            time.sleep(0.25)
        self._pick_from_open_gui(item, geo["char"])
        self.input.click(geo[slot][0], geo[slot][1], 1, 30)
        time.sleep(0.4)
        st = self.state()
        if st.get("cursor"):
            raise RuntimeError(f"could not place {item} into {entity_name}.{slot}")
        self.input.tap(SCANCODES["e"], 60)
        time.sleep(0.5)
        return self.state()

    def entity_take(self, x: float, y: float, entity_name: str,
                    slot: str = "output") -> dict:
        """Open an entity and Ctrl+click its slot to fast-transfer to player."""
        geo = self.ENTITY_GUI.get(entity_name)
        if not geo:
            raise RuntimeError(f"no GUI layout known for {entity_name}")
        before = {i["name"]: int(i["count"]) for i in self.state().get("inventory", [])}
        self.open_entity(x, y)
        self.mod_click(geo[slot][0], geo[slot][1], "ctrl")
        st = self.state()
        if st.get("cursor"):
            # fast transfer should not leave anything on the cursor; put it back
            self.input.tap(SCANCODES["q"], 50)
            time.sleep(0.25)
        gained = {}
        for i in st.get("inventory", []):
            n = int(i["count"]) - before.get(i["name"], 0)
            if n > 0:
                gained[i["name"]] = n
        self.input.tap(SCANCODES["e"], 60)
        time.sleep(0.5)
        return {"ok": bool(gained), "gained": gained,
                "inventory": self.state().get("inventory")}

    def pick_ground(self, x: float, y: float) -> dict:
        """Pick up item-on-ground at a world position with F."""
        self.close_all_ui()
        before = {i["name"]: int(i["count"]) for i in self.state().get("inventory", [])}
        self.aim_world(x, y)
        self.input.tap(SCANCODES["f"], 50)
        time.sleep(0.6)
        st = self.state()
        gained = {i["name"]: int(i["count"]) - before.get(i["name"], 0)
                  for i in st.get("inventory", [])
                  if int(i["count"]) > before.get(i["name"], 0)}
        return {"ok": bool(gained), "gained": gained,
                "inventory": st.get("inventory")}

    # ----------------------------------------------------------------- detect
    def open_entity(self, x: float, y: float) -> dict:
        self.ensure_character()
        self.close_all_ui()
        st = self.state()
        if st.get("cursor"):
            self.input.tap(SCANCODES["q"], 50)
            time.sleep(0.25)
        px, py = st["pos"]["x"], st["pos"]["y"]
        if math.hypot(x - px, y - py) > 8.5:
            self.walk_to(x, y, tolerance=6.0, timeout=120)
            st = self.state()
        st = self.aim_world(x, y)
        self.input.click_pair(1, 40)
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
