#!/usr/bin/env python3
"""MCP stdio server for client-side input and read-only client memory/Lua control.

This server has no RCON/scenario dependency.  It attaches to a running Factorio
window and exposes normal keyboard/mouse/screenshot operations.  Use it when
the target server has no AgentBridge scenario, e.g. a vanilla freeplay host.

Config example:
  {
    "mcpServers": {
      "factorio-client": {
        "command": "python",
        "args": ["-m", "bridge.client_mcp_server"],
        "cwd": "<ABSOLUTE_PATH_TO_FactorioAgent>",
        "env": {"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
      }
    }
  }
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from pathlib import Path

from .client_control import ClientController, find_windows


TOOLS = [
    {"name": "client_list_windows", "description": "List visible Factorio windows (hwnd, pid, title).",
     "inputSchema": {"type": "object", "properties": {
         "title": {"type": "string", "default": "(?i)factorio"}, "pid": {"type": "integer"}}}},
    {"name": "client_attach", "description": "Attach to a running Factorio window by hwnd/pid/title.",
     "inputSchema": {"type": "object", "properties": {
         "hwnd": {"type": "integer"}, "pid": {"type": "integer"},
         "title": {"type": "string", "default": "(?i)factorio"}}}},
    {"name": "client_info", "description": "Return attached window info and client-area size.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "client_focus", "description": "Restore and force the attached game window to the foreground. Required before input.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "client_screenshot", "description": "Capture the attached window. Returns a PNG path; set inline=true to also return the image as MCP image content.",
     "inputSchema": {"type": "object", "properties": {
         "output": {"type": "string", "default": "state/shots/client.png"},
         "scale": {"type": "number"}, "inline": {"type": "boolean", "default": False}}}},
    {"name": "client_key", "description": "Send one normal key event (tap/down/up). Keys: wasd, e, m, q, r, t, tab, esc, enter, space, shift, ctrl, alt, tilde, digits, or VK number/0x..",
     "inputSchema": {"type": "object", "properties": {
         "key": {"type": "string"}, "action": {"type": "string", "enum": ["tap", "down", "up"], "default": "tap"}},
         "required": ["key"]}},
    {"name": "client_hold", "description": "Hold a key for N milliseconds. Aborts if the game window loses foreground.",
     "inputSchema": {"type": "object", "properties": {
         "key": {"type": "string"}, "ms": {"type": "integer", "default": 500}},
         "required": ["key"]}},
    {"name": "client_walk", "description": "Hold a movement key (W/A/S/D or up/down/left/right) for N seconds.",
     "inputSchema": {"type": "object", "properties": {
         "direction": {"type": "string"}, "seconds": {"type": "number", "default": 1}},
         "required": ["direction"]}},
    {"name": "client_click", "description": "Click at client-area coordinates. hold_ms>0 mines/holds the mouse button; double=true double-clicks.",
     "inputSchema": {"type": "object", "properties": {
         "x": {"type": "number"}, "y": {"type": "number"},
         "button": {"type": "string", "enum": ["left", "right"], "default": "left"},
         "hold_ms": {"type": "integer", "default": 0}, "double": {"type": "boolean", "default": False}},
         "required": ["x", "y"]}},
    {"name": "client_scroll", "description": "Scroll the mouse wheel (positive/negative).",
     "inputSchema": {"type": "object", "properties": {"amount": {"type": "integer", "default": 120}}}},
    {"name": "client_type", "description": "Type ASCII text into the focused game (chat/console). Newlines press Enter.",
     "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},
    {"name": "client_map", "description": "Toggle the Factorio map (M). Use with screenshots to find ore/landmarks.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "client_inventory", "description": "Toggle the player inventory (E).",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "client_input_attach", "description": "Attach a persistent background input channel (Frida SDL injection). Works without window focus. Keep it attached for the whole bot session; keyboard/walking work while minimized.",
     "inputSchema": {"type": "object", "properties": {"pid": {"type": "integer"}}}},
    {"name": "client_input_status", "description": "Status of the background input channel and its virtual mouse.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "client_input_key", "description": "Background key event via SDL. Works without focus. Keys: wasd, e, m, q, r, t, f, tab, esc, enter, space, shift, ctrl, alt, tilde, digits, f1-f12, or a scancode.",
     "inputSchema": {"type": "object", "properties": {
         "key": {"type": "string"}, "action": {"type": "string", "enum": ["tap", "down", "up"], "default": "tap"},
         "ms": {"type": "integer", "default": 40}}, "required": ["key"]}},
    {"name": "client_input_walk", "description": "Walk in a direction (north/south/east/west/nw/ne/sw/se) for N seconds using background SDL key state.",
     "inputSchema": {"type": "object", "properties": {
         "direction": {"type": "string"}, "seconds": {"type": "number", "default": 1}}, "required": ["direction"]}},
    {"name": "client_input_text", "description": "Type text through SDL (chat/console). Background; does not require focus.",
     "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},
    {"name": "client_input_move", "description": "Move the virtual mouse to SDL client coordinates (the game's display resolution, e.g. 3440x1440). Background; no focus needed. Real mouse events are hidden while active.",
     "inputSchema": {"type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}}, "required": ["x", "y"]}},
    {"name": "client_input_click", "description": "Low-level click at SDL client coordinates. GUI clicks and hover/selection work; for world actions prefer client_action_mine/client_action_build.",
     "inputSchema": {"type": "object", "properties": {
         "x": {"type": "number"}, "y": {"type": "number"},
         "button": {"type": "string", "enum": ["left", "right", "middle"], "default": "left"},
         "hold_ms": {"type": "integer", "default": 0}, "double": {"type": "boolean", "default": False}},
         "required": ["x", "y"]}},
    {"name": "client_input_world_click", "description": "Click at a world offset relative to the screen centre (player). dx_tiles/dy_tiles are east/south offsets; px_per_tile defaults to 64 at zoom 1.5.",
     "inputSchema": {"type": "object", "properties": {
         "dx_tiles": {"type": "number"}, "dy_tiles": {"type": "number"},
         "px_per_tile": {"type": "number", "default": 64},
         "button": {"type": "string", "enum": ["left", "right", "middle"], "default": "left"},
         "hold_ms": {"type": "integer", "default": 0}},
         "required": ["dx_tiles", "dy_tiles"]}},
    {"name": "client_input_mouse_off", "description": "Disable the virtual mouse and stop hiding real mouse events.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "client_input_detach", "description": "Detach the background input channel.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "client_action_attach", "description": "Attach the high-level background action agent (walk/mine/pick/build/open) to a running client. It automatically leaves remote view (presses M when needed) and uses the persistent SDL input + read-only Lua state.",
     "inputSchema": {"type": "object", "properties": {
         "pid": {"type": "integer"}, "name": {"type": "string", "description": "bot player name"}}}},
    {"name": "client_action_state", "description": "High-level state: controller, position, selected entity, mining, cursor item, inventory, opened-self, virtual mouse. Works in the background.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "client_action_mine", "description": "Mine the nearest resource of a type in the background: aim with the virtual mouse, hold the right button, stop by moving the cursor to a blank tile, verify inventory. Requires the character controller (auto).",
     "inputSchema": {"type": "object", "properties": {
         "resource": {"type": "string", "default": "iron-ore"},
         "count": {"type": "integer", "default": 1},
         "radius": {"type": "number", "default": 16},
         "timeout": {"type": "number", "default": 25}}, "required": []}},
    {"name": "client_action_pick", "description": "Pick an item from the character's main inventory into the cursor via background GUI clicks. Inventory slot geometry defaults to a 3440x1440 client.",
     "inputSchema": {"type": "object", "properties": {"item": {"type": "string"}}, "required": ["item"]}},
    {"name": "client_action_build", "description": "Build/pick an item and place it at a world position in the background. on_ore=true for a mining drill; build drills before starting a mining hold, because the client keeps the right button held after background mining.",
     "inputSchema": {"type": "object", "properties": {
         "item": {"type": "string"}, "x": {"type": "number"}, "y": {"type": "number"},
         "on_ore": {"type": "boolean", "default": False},
         "direction": {"type": "integer"}}, "required": ["item", "x", "y"]}},
    {"name": "client_action_open", "description": "Left-click an entity to open its GUI in the background (empty the cursor first). Verification of the opened GUI requires a screenshot; use client_action_close_ui after.",
     "inputSchema": {"type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}}, "required": ["x", "y"]}},
    {"name": "client_action_mine_entity", "description": "Mine the nearest tree/rock/simple entity by type or name in the background: tile-BFS walking to it, right-hold, stop on a blank tile. Use item='wood' to verify tree chopping.",
     "inputSchema": {"type": "object", "properties": {
         "name": {"type": "string"}, "type": {"type": "string"},
         "item": {"type": "string"}, "radius": {"type": "number", "default": 64},
         "timeout": {"type": "number", "default": 120}}, "required": []}},
    {"name": "client_action_craft", "description": "Hand-craft a recipe through the character-screen crafting GUI: Ctrl+F search, type the query, click the first result. Normal UI input; works in the background.",
     "inputSchema": {"type": "object", "properties": {
         "query": {"type": "string"}, "count": {"type": "integer", "default": 1},
         "timeout": {"type": "number", "default": 20}}, "required": ["query"]}},
    {"name": "client_action_insert", "description": "Open an entity and move one player stack of an item into one of its slots (input/fuel/slot1) with background GUI clicks. Built-in layouts: stone furnace, burner mining drill, wooden chest (3440x1440 UI 1.25).",
     "inputSchema": {"type": "object", "properties": {
         "x": {"type": "number"}, "y": {"type": "number"},
         "entity": {"type": "string"}, "item": {"type": "string"},
         "slot": {"type": "string", "default": "input"}}, "required": ["x", "y", "entity", "item"]}},
    {"name": "client_action_take", "description": "Open an entity and Ctrl+click a slot to fast-transfer its contents into the player inventory (works for furnace output/fuel and chest slots).",
     "inputSchema": {"type": "object", "properties": {
         "x": {"type": "number"}, "y": {"type": "number"},
         "entity": {"type": "string"}, "slot": {"type": "string", "default": "output"}},
         "required": ["x", "y", "entity"]}},
    {"name": "client_action_pick_ground", "description": "Pick up item-on-ground at a world position with F (e.g. burner mining drill output, which drops at drop_position).",
     "inputSchema": {"type": "object", "properties": {
         "x": {"type": "number"}, "y": {"type": "number"}}, "required": ["x", "y"]}},
    {"name": "client_auto_start", "description": "Start the unattended burner-era loop in a background thread: collect ore from the drop chest, load the furnace, collect plates, share coal, hand-craft work orders, return to the anchor. All normal client input; needs client_action_attach first.",
     "inputSchema": {"type": "object", "properties": {
         "drill": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2},
         "chest": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2},
         "furnace": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2},
         "anchor": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2},
         "orders": {"type": "object", "description": "recipe query -> target count"},
         "interval": {"type": "number", "default": 20},
         "minutes": {"type": "number", "default": 6}},
         "required": ["drill", "chest", "furnace"]}},
    {"name": "client_auto_status", "description": "Status and counters of the unattended burner loop.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "client_auto_stop", "description": "Stop the unattended burner loop.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "client_action_walk_to", "description": "Walk to a world position with a tile-collision BFS (client Lua collision grid) and automatic replanning. Background; tolerance defaults to 0.8 tiles.",
     "inputSchema": {"type": "object", "properties": {
         "x": {"type": "number"}, "y": {"type": "number"},
         "tolerance": {"type": "number", "default": 0.8},
         "timeout": {"type": "number", "default": 30}}, "required": ["x", "y"]}},
    {"name": "client_action_stop", "description": "Stop mining and release all virtual mouse buttons; moves the cursor to a blank tile first.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "client_action_close_ui", "description": "Close the character/inventory GUI (E) or an entity GUI (Escape) when open.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "client_action_status", "description": "Controller and state of the high-level background action agent.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "client_action_detach", "description": "Detach the high-level background action agent.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "client_memory_attach", "description": "Attach a read-only Frida Lua bridge to the client process. Works while the game is background/minimized; does not require window focus. Requires frida on the host.",
     "inputSchema": {"type": "object", "properties": {
         "pid": {"type": "integer"}, "name": {"type": "string", "description": "bot player name"}}}},
    {"name": "client_memory_status", "description": "Status of the attached read-only client memory/Lua bridge.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "client_memory_observe", "description": "Read authoritative client-side Lua state: player position, health, main inventory, nearby resources/entities, tick, surface. Works in the background; no screenshots.",
     "inputSchema": {"type": "object", "properties": {
         "radius": {"type": "number", "default": 32}, "name": {"type": "string"}}}},
    {"name": "client_memory_inventory", "description": "Read the player's main inventory from client memory/Lua state.",
     "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}}}},
    {"name": "client_memory_detach", "description": "Detach the Frida Lua bridge.",
     "inputSchema": {"type": "object", "properties": {}}},
]


class ClientMcpServer:
    def __init__(self, hwnd: int | None = None, pid: int | None = None,
                 title: str = r"(?i)factorio"):
        self.ctrl: ClientController | None = None
        if hwnd is not None or pid is not None:
            self.ctrl = ClientController(hwnd=hwnd, pid=pid, title_regex=title)
        self.mem = None
        self.memory_name = None
        self.input = None
        self.actions = None
        self.auto = None

    def _client(self) -> ClientController:
        if self.ctrl is None:
            self.ctrl = ClientController()
        return self.ctrl

    def _call(self, name: str, args: dict) -> tuple[str, bool, dict | None]:
        if name == "client_list_windows":
            return json.dumps(find_windows(args.get("title", r"(?i)factorio"),
                                           args.get("pid")), ensure_ascii=False), True, None
        if name == "client_attach":
            self.ctrl = ClientController(hwnd=args.get("hwnd"), pid=args.get("pid"),
                                         title_regex=args.get("title", r"(?i)factorio"))
            return json.dumps(self.ctrl.info(), ensure_ascii=False), True, None
        c = self._client()
        if name == "client_info":
            return json.dumps(c.info(), ensure_ascii=False), True, None
        if name == "client_focus":
            return json.dumps(c.focus(), ensure_ascii=False), True, None
        if name == "client_screenshot":
            out = c.screenshot(args.get("output", "state/shots/client.png"),
                               args.get("scale"))
            img = None
            if args.get("inline") and out.get("path"):
                p = Path(out["path"])
                img = {"type": "image", "mimeType": "image/png",
                       "data": base64.b64encode(p.read_bytes()).decode("ascii")}
            return json.dumps(out, ensure_ascii=False), True, img
        if name == "client_key":
            return json.dumps(c.key(args["key"], args.get("action", "tap")),
                              ensure_ascii=False), True, None
        if name == "client_hold":
            return json.dumps(c.hold(args["key"], int(args.get("ms", 500))),
                              ensure_ascii=False), True, None
        if name == "client_walk":
            return json.dumps(c.walk(args["direction"], float(args.get("seconds", 1))),
                              ensure_ascii=False), True, None
        if name == "client_click":
            return json.dumps(c.click(float(args["x"]), float(args["y"]),
                                      args.get("button", "left"),
                                      int(args.get("hold_ms", 0)),
                                      bool(args.get("double", False))),
                              ensure_ascii=False), True, None
        if name == "client_scroll":
            return json.dumps(c.scroll(int(args.get("amount", 120))), ensure_ascii=False), True, None
        if name == "client_type":
            return json.dumps(c.type_text(args["text"]), ensure_ascii=False), True, None
        if name == "client_map":
            return json.dumps(c.map_toggle(), ensure_ascii=False), True, None
        if name == "client_inventory":
            return json.dumps(c.inventory_toggle(), ensure_ascii=False), True, None
        if name == "client_input_attach":
            from .client_input import ClientInput
            ipid = args.get("pid") or c.pid
            if self.input:
                self.input.close()
            self.input = ClientInput(int(ipid))
            return json.dumps({"info": self.input.info(), "state": self.input.state()},
                              ensure_ascii=False), True, None
        if name == "client_input_status":
            if not self.input:
                raise RuntimeError("background input channel is not attached")
            return json.dumps({"info": self.input.info(), "state": self.input.state()},
                              ensure_ascii=False), True, None
        if name == "client_input_key":
            if not self.input:
                raise RuntimeError("background input channel is not attached")
            from .client_input import scancode_for
            sc = scancode_for(args["key"])
            action = args.get("action", "tap")
            if action == "tap":
                out = self.input.tap(sc, int(args.get("ms", 40)))
            else:
                out = self.input.key(sc, action == "down")
            return json.dumps(out, ensure_ascii=False), True, None
        if name == "client_input_walk":
            if not self.input:
                raise RuntimeError("background input channel is not attached")
            from .client_input import DIRS, SCANCODES
            keys = DIRS.get(str(args["direction"]).lower())
            if not keys:
                raise ValueError(f"unknown direction {args['direction']!r}")
            for k in keys:
                self.input.key(SCANCODES[k], True)
            time.sleep(float(args.get("seconds", 1)))
            for k in keys:
                self.input.key(SCANCODES[k], False)
            return json.dumps({"ok": True, "direction": args["direction"],
                               "seconds": float(args.get("seconds", 1))},
                              ensure_ascii=False), True, None
        if name == "client_input_text":
            if not self.input:
                raise RuntimeError("background input channel is not attached")
            return json.dumps(self.input.text(args["text"]), ensure_ascii=False), True, None
        if name == "client_input_move":
            if not self.input:
                raise RuntimeError("background input channel is not attached")
            return json.dumps(self.input.move(float(args["x"]), float(args["y"])),
                              ensure_ascii=False), True, None
        if name == "client_input_click":
            if not self.input:
                raise RuntimeError("background input channel is not attached")
            btn = {"left": 1, "right": 3, "middle": 2}.get(args.get("button", "left"), 1)
            out = self.input.click(float(args["x"]), float(args["y"]), btn,
                                   int(args.get("hold_ms", 0)), bool(args.get("double", False)))
            return json.dumps(out, ensure_ascii=False), True, None
        if name == "client_input_world_click":
            if not self.input:
                raise RuntimeError("background input channel is not attached")
            info = self.input.info()
            win = (info.get("windows") or [{}])[0]
            w = float(win.get("w") or 3440)
            h = float(win.get("h") or 1440)
            scale = float(args.get("px_per_tile", 64))
            x = w / 2.0 + float(args["dx_tiles"]) * scale
            y = h / 2.0 + float(args["dy_tiles"]) * scale
            btn = {"left": 1, "right": 3, "middle": 2}.get(args.get("button", "left"), 1)
            out = self.input.click(x, y, btn, int(args.get("hold_ms", 0)), False)
            out.update({"x": x, "y": y, "px_per_tile": scale})
            return json.dumps(out, ensure_ascii=False), True, None
        if name == "client_input_mouse_off":
            if self.input:
                return json.dumps(self.input.disable(), ensure_ascii=False), True, None
            return json.dumps({"ok": True, "active": False}, ensure_ascii=False), True, None
        if name == "client_input_detach":
            if self.input:
                self.input.close()
                self.input = None
            return json.dumps({"ok": True}, ensure_ascii=False), True, None
        if (name.startswith("client_action_") and self.auto and self.auto.running
                and name not in ("client_action_state", "client_action_status")):
            raise RuntimeError("autopilot is running; call client_auto_stop first")
        if name == "client_action_attach":
            from .client_actions import ClientActions
            apid = args.get("pid") or c.pid
            if self.actions:
                self.actions.close()
            self.actions = ClientActions(int(apid), args.get("name"))
            return json.dumps({"state": self.actions.state()}, ensure_ascii=False), True, None
        if name == "client_action_state":
            if not self.actions:
                raise RuntimeError("high-level action agent is not attached")
            return json.dumps(self.actions.state(), ensure_ascii=False), True, None
        if name == "client_action_mine":
            if not self.actions:
                raise RuntimeError("high-level action agent is not attached")
            out = self.actions.mine_nearest(
                args.get("resource", "iron-ore"), int(args.get("count", 1)),
                float(args.get("radius", 16)), float(args.get("timeout", 25)))
            return json.dumps(out, ensure_ascii=False), True, None
        if name == "client_action_pick":
            if not self.actions:
                raise RuntimeError("high-level action agent is not attached")
            return json.dumps(self.actions.pick_item(args["item"]), ensure_ascii=False), True, None
        if name == "client_action_build":
            if not self.actions:
                raise RuntimeError("high-level action agent is not attached")
            out = self.actions.build_item(
                args["item"], float(args["x"]), float(args["y"]),
                bool(args.get("on_ore", False)),
                int(args["direction"]) if args.get("direction") is not None else None)
            return json.dumps(out, ensure_ascii=False), True, None
        if name == "client_action_open":
            if not self.actions:
                raise RuntimeError("high-level action agent is not attached")
            return json.dumps(self.actions.open_entity(float(args["x"]), float(args["y"])),
                              ensure_ascii=False), True, None
        if name == "client_action_mine_entity":
            if not self.actions:
                raise RuntimeError("high-level action agent is not attached")
            out = self.actions.mine_entity(
                args.get("name"), args.get("type"), args.get("item"),
                float(args.get("radius", 64)), float(args.get("timeout", 120)))
            return json.dumps(out, ensure_ascii=False), True, None
        if name == "client_action_craft":
            if not self.actions:
                raise RuntimeError("high-level action agent is not attached")
            out = self.actions.craft(args["query"], int(args.get("count", 1)),
                                     float(args.get("timeout", 20)))
            return json.dumps(out, ensure_ascii=False), True, None
        if name == "client_action_insert":
            if not self.actions:
                raise RuntimeError("high-level action agent is not attached")
            out = self.actions.entity_insert(
                float(args["x"]), float(args["y"]), args["entity"], args["item"],
                args.get("slot", "input"))
            return json.dumps(out, ensure_ascii=False), True, None
        if name == "client_action_take":
            if not self.actions:
                raise RuntimeError("high-level action agent is not attached")
            out = self.actions.entity_take(
                float(args["x"]), float(args["y"]), args["entity"],
                args.get("slot", "output"))
            return json.dumps(out, ensure_ascii=False), True, None
        if name == "client_action_pick_ground":
            if not self.actions:
                raise RuntimeError("high-level action agent is not attached")
            out = self.actions.pick_ground(float(args["x"]), float(args["y"]))
            return json.dumps(out, ensure_ascii=False), True, None
        if name == "client_auto_start":
            if not self.actions:
                raise RuntimeError("high-level action agent is not attached")
            if self.auto and self.auto.running:
                raise RuntimeError("autopilot already running")
            from .client_autopilot import BurnerAutopilot, Layout
            layout = Layout(drill=tuple(args["drill"]), chest=tuple(args["chest"]),
                            furnace=tuple(args["furnace"]),
                            anchor=tuple(args["anchor"]) if args.get("anchor") else None)
            self.auto = BurnerAutopilot(
                self.actions, layout, orders=args.get("orders") or {},
                interval=float(args.get("interval", 20)),
                state_path="state/autopilot_state.json",
                log=lambda msg: print(msg, file=sys.stderr, flush=True))
            self.auto.start(float(args.get("minutes", 6)))
            return json.dumps({"ok": True, "status": self.auto.status()},
                              ensure_ascii=False), True, None
        if name == "client_auto_status":
            if not self.auto:
                return json.dumps({"ok": False, "running": False,
                                   "reason": "not started"}, ensure_ascii=False), True, None
            return json.dumps({"ok": True, **self.auto.status()}, ensure_ascii=False), True, None
        if name == "client_auto_stop":
            if self.auto:
                self.auto.stop()
            return json.dumps({"ok": True, "running": bool(self.auto and self.auto.running)},
                              ensure_ascii=False), True, None
        if name == "client_action_walk_to":
            if not self.actions:
                raise RuntimeError("high-level action agent is not attached")
            return json.dumps(self.actions.walk_to(
                float(args["x"]), float(args["y"]),
                float(args.get("tolerance", 0.8)), float(args.get("timeout", 30))),
                ensure_ascii=False), True, None
        if name == "client_action_stop":
            if not self.actions:
                raise RuntimeError("high-level action agent is not attached")
            return json.dumps(self.actions.stop_mining(), ensure_ascii=False), True, None
        if name == "client_action_close_ui":
            if not self.actions:
                raise RuntimeError("high-level action agent is not attached")
            return json.dumps(self.actions.close_all_ui(), ensure_ascii=False), True, None
        if name == "client_action_status":
            if not self.actions:
                raise RuntimeError("high-level action agent is not attached")
            return json.dumps({"controller": self.actions.controller_type(),
                               "state": self.actions.state()}, ensure_ascii=False), True, None
        if name == "client_action_detach":
            if self.auto:
                self.auto.stop()
                self.auto = None
            if self.actions:
                self.actions.close()
                self.actions = None
            return json.dumps({"ok": True}, ensure_ascii=False), True, None
        if name == "client_memory_attach":
            from .client_memory import ClientMemory
            mpid = args.get("pid") or c.pid
            self.mem = ClientMemory(pid=int(mpid))
            self.memory_name = args.get("name")
            return json.dumps(self.mem.status(), ensure_ascii=False), True, None
        if name == "client_memory_status":
            if not self.mem:
                raise RuntimeError("client memory bridge is not attached")
            return json.dumps(self.mem.status(), ensure_ascii=False), True, None
        if name == "client_memory_observe":
            if not self.mem:
                raise RuntimeError("client memory bridge is not attached")
            raw = self.mem.observe(args.get("name") or self.memory_name,
                                   float(args.get("radius", 32)))
            val = raw.get("value") if isinstance(raw, dict) and raw.get("ok") else raw
            return json.dumps(val, ensure_ascii=False), True, None
        if name == "client_memory_inventory":
            if not self.mem:
                raise RuntimeError("client memory bridge is not attached")
            raw = self.mem.inventory(args.get("name") or self.memory_name)
            val = raw.get("value") if isinstance(raw, dict) and raw.get("ok") else raw
            return json.dumps(val, ensure_ascii=False), True, None
        if name == "client_memory_detach":
            if self.mem:
                self.mem.close()
                self.mem = None
            return json.dumps({"ok": True}, ensure_ascii=False), True, None
        raise ValueError(f"unknown tool {name}")

    def handle(self, msg: dict):
        method, mid = msg.get("method"), msg.get("id")
        if method == "initialize":
            return {"jsonrpc": "2.0", "id": mid, "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "factorio-client-control", "version": "0.3.8"},
                "instructions": (
                    "Client-side input control for a running Factorio window. "
                    "Call client_list_windows/client_attach, client_focus, then use "
                    "client_screenshot + client_key/client_walk/client_click. "
                    "client_action_* attaches a high-level background action agent: walk, mine, "
                    "pick items from inventory, build on the ground, and open entity GUIs without "
                    "window focus. It auto-leaves remote view (M). Mining holds the right mouse and "
                    "stops by moving the cursor to a blank tile; build drills on ore before a mining "
                    "hold. Ordinary server-side scenario tools remain the most robust route when the "
                    "server is yours."),
            }}
        if method in ("notifications/initialized", "initialized", "ping"):
            return None if method != "ping" else {"jsonrpc": "2.0", "id": mid, "result": {}}
        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}}
        if method == "tools/call":
            params = msg.get("params") or {}
            name = params.get("name", "")
            args = params.get("arguments") or {}
            try:
                text, ok, image = self._call(name, args)
                content = [{"type": "text", "text": text}]
                if image:
                    content.append(image)
                return {"jsonrpc": "2.0", "id": mid, "result": {
                    "content": content, "isError": not ok}}
            except Exception as e:
                return {"jsonrpc": "2.0", "id": mid, "result": {
                    "content": [{"type": "text",
                                 "text": f"{type(e).__name__}: {e}"}], "isError": True}}
        if method in ("shutdown", "exit"):
            return {"jsonrpc": "2.0", "id": mid, "result": {}}
        if mid is None:
            return None
        return {"jsonrpc": "2.0", "id": mid,
                "error": {"code": -32601, "message": f"method not found: {method}"}}


def _read(stream):
    line = stream.readline()
    if not line:
        return None
    return json.loads(line.decode("utf-8"))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
        sys.stderr.reconfigure(encoding="utf-8", newline="\n")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="MCP client-side Factorio controller")
    ap.add_argument("--hwnd", type=int)
    ap.add_argument("--pid", type=int)
    ap.add_argument("--title", default=r"(?i)factorio")
    a = ap.parse_args()
    server = ClientMcpServer(a.hwnd, a.pid, a.title)
    out = sys.stdout
    print("[mcp-client] input + read-only memory Factorio control", file=sys.stderr, flush=True)
    while True:
        try:
            msg = _read(sys.stdin.buffer)
        except Exception as e:
            print(f"[mcp-client] read error: {e}", file=sys.stderr)
            break
        if msg is None:
            break
        try:
            resp = server.handle(msg)
        except Exception as e:
            resp = {"jsonrpc": "2.0", "id": msg.get("id"),
                    "error": {"code": -32603, "message": str(e)}}
        if resp is not None:
            out.write(json.dumps(resp, ensure_ascii=False) + "\n")
            out.flush()


if __name__ == "__main__":
    main()
