"""High-level agent interface: one embodied Factorio character over RCON."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .rcon import RconClient, call_interface, lua_quote

INTERFACE = "agentbridge"
BLUEPRINT_DIR = Path(__file__).resolve().parents[1] / "state" / "blueprints"


def _lua_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if value is None:
        return "nil"
    return lua_quote(str(value))


def _call(rc: RconClient, method: str, *args: Any) -> str:
    rendered = ", ".join(_lua_value(a) for a in args)
    command = f'/c remote.call({lua_quote(INTERFACE)}, {lua_quote(method)}'
    if rendered:
        command += ", " + rendered
    command += ")"
    return rc.execute(command)


def _parse(text: str) -> Any:
    text = text.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


class AgentBridge:
    """Synchronous facade over the agentbridge mod.

    Usage::

        with AgentBridge() as agent:
            print(agent.observe_text())
            agent.perform("walk", x=10, y=10)
            agent.perform("mine", name="iron-ore", count=5)
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 27016,
                 password: str = "test", timeout: float = 15.0,
                 auto_connect: bool = True):
        self.rc = RconClient(host, port, password, timeout=timeout)
        self._warmed = False
        if auto_connect:
            self.connect()

    # -- connection ---------------------------------------------------------

    def connect(self) -> "AgentBridge":
        self.rc.connect()
        self.warmup()
        return self

    def warmup(self) -> None:
        """Consume the one-shot 'Lua disables achievements' confirmation.

        The first Lua console command after loading a save is swallowed by the
        game and only logged.  Sending a harmless command twice guarantees that
        the mod interface is usable.  We deliberately do not rely on the log
        text because it is not returned over RCON.
        """
        for _ in range(2):
            self.rc.execute('/c rcon.print("__agentbridge_warmup__")')
        _call(self.rc, "ensure")
        self._warmed = True

    def close(self) -> None:
        self.rc.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # -- primitives ---------------------------------------------------------

    def state(self, radius: float | None = None) -> dict:
        args = () if radius is None else (radius,)
        for _ in range(2):
            data = _parse(_call(self.rc, "state", *args))
            if isinstance(data, dict):
                return data
            time.sleep(0.2)
        raise RuntimeError(f"agentbridge.state returned no JSON: {data!r}")

    def submit(self, action: dict) -> dict:
        data = _parse(_call(self.rc, "submit", json.dumps(action, ensure_ascii=False)))
        if not isinstance(data, dict):
            raise RuntimeError(f"submit failed: {data!r}")
        return data

    def wait_idle(self, timeout: float = 180.0, poll: float = 0.5,
                  cancel_on_timeout: bool = False) -> dict:
        """Wait until the current job and the queue are empty."""
        deadline = time.time() + timeout
        last: dict = {}
        while time.time() < deadline:
            last = self.state()
            if not last.get("job") and not last.get("queue"):
                return last
            time.sleep(poll)
        if cancel_on_timeout:
            self.cancel_all()
        return last

    def wait_job(self, job_id: int, timeout: float = 180.0, poll: float = 0.4) -> dict:
        """Wait until a job leaves the running/queued set and find its terminal event."""
        deadline = time.time() + timeout
        seen = False
        last: dict = {}
        terminal_types = ("job_done", "job_failed", "job_canceled")
        while time.time() < deadline:
            last = self.state()
            running = last.get("job") or {}
            queued = {q.get("id") for q in (last.get("queue") or [])}
            if running.get("id") == job_id or job_id in queued:
                seen = True
                time.sleep(poll)
                continue
            events = self.events(0).get("events", [])
            terminal = [e for e in events if e.get("id") == job_id and e.get("type") in terminal_types]
            if terminal:
                return {"state": last, "result": terminal[-1]}
            if seen:
                # It left the queue but the terminal event hasn't been flushed yet.
                time.sleep(poll)
                last = self.state()
                events = self.events(0).get("events", [])
                terminal = [e for e in events if e.get("id") == job_id and e.get("type") in terminal_types]
                return {"state": last, "result": terminal[-1] if terminal else None}
            time.sleep(poll)
        return {"state": last or self.state(), "result": None, "timeout": True}

    def events(self, since: int = 0) -> dict:
        data = _parse(_call(self.rc, "events", since))
        return data if isinstance(data, dict) else {"events": [], "last_seq": since}

    def perform(self, kind: str, wait: bool = True, timeout: float = 180.0, **params) -> dict:
        action = {"kind": kind, **params}
        result = self.submit(action)
        job_id = result.get("id")
        if not wait or not job_id:
            return result
        final = self.wait_job(job_id, timeout=timeout)
        return {"submitted": result, "state": final.get("state"), "result": final.get("result"),
                "timeout": bool(final.get("timeout"))}

    def cancel(self, job_id: int | None = None) -> dict:
        text = _call(self.rc, "cancel", job_id) if job_id is not None else _call(self.rc, "cancel")
        data = _parse(text)
        return data if isinstance(data, dict) else {"ok": False}

    def cancel_all(self) -> dict:
        data = _parse(_call(self.rc, "cancel_all"))
        return data if isinstance(data, dict) else {"ok": False}

    def find_water(self, radius: float = 120) -> dict:
        return _parse(_call(self.rc, "find_water", radius)) or {"ok": False}

    def scan(self, radius: float = 18) -> dict:
        data = _parse(_call(self.rc, "scan", radius))
        return data if isinstance(data, dict) else {"ok": False}

    def nearby_entities(self, radius: float = 32, name: str | None = None,
                        entity_type: str | None = None,
                        include_resources: bool = False,
                        include_nature: bool = True,
                        limit: int = 50) -> dict:
        scan = self.scan(radius)
        if not isinstance(scan, dict) or not scan.get("ok"):
            return scan if isinstance(scan, dict) else {"ok": False}
        items = list(scan.get("entities") or [])
        if include_resources:
            for r in scan.get("resources") or []:
                nearest = r.get("nearest") or {}
                items.append({"name": r.get("name"), "type": "resource",
                              "x": nearest.get("x"), "y": nearest.get("y"),
                              "distance": nearest.get("distance"),
                              "tiles": r.get("tiles"),
                              "total_amount": r.get("total_amount")})
        nature = {"tree", "fish", "simple-entity", "optimized-tree",
                  "smoke-with-trigger", "fire", "particle", "decorative"}
        out = []
        for item in items:
            if not include_nature and item.get("type") in nature:
                continue
            if name and name.lower() not in str(item.get("name", "")).lower():
                continue
            if entity_type and item.get("type") != entity_type:
                continue
            out.append(item)
        out.sort(key=lambda e: e.get("distance") if e.get("distance") is not None else 1e9)
        return {"ok": True, "radius": radius, "count": len(out),
                "entities": out[:max(1, int(limit))]}

    def recipe(self, name: str) -> dict:
        data = _parse(_call(self.rc, "recipe", name))
        return data if isinstance(data, dict) else {"ok": False}

    def techs(self, limit: int = 40) -> dict:
        data = _parse(_call(self.rc, "techs", limit))
        return data if isinstance(data, dict) else {"ok": False}

    def pause(self, flag: bool = True) -> dict:
        return _parse(_call(self.rc, "pause", flag)) or {}

    def resume(self) -> dict:
        return self.pause(False)

    def speed(self, value: float) -> dict:
        return _parse(_call(self.rc, "speed", value)) or {}

    def save(self) -> dict:
        return _parse(_call(self.rc, "save")) or {}

    def respawn(self, x: float | None = None, y: float | None = None) -> dict:
        if x is None or y is None:
            return _parse(_call(self.rc, "respawn")) or {}
        return _parse(_call(self.rc, "respawn", x, y)) or {}

    # -- scenario / real player ---------------------------------------------

    def set_bot_name(self, name: str) -> dict:
        return _parse(_call(self.rc, "set_bot_name", name)) or {}

    def set_bare(self, flag: bool) -> dict:
        return _parse(_call(self.rc, "set_bare", flag)) or {}

    def instruct(self, text: str, player_index: int | None = None) -> dict:
        if player_index is None:
            return _parse(_call(self.rc, "instruct", text)) or {}
        return _parse(_call(self.rc, "instruct", text, player_index)) or {}

    def clear_inbox(self) -> dict:
        return _parse(_call(self.rc, "clear_inbox")) or {}

    def set_eval(self, flag: bool) -> dict:
        return _parse(_call(self.rc, "set_eval", flag)) or {}

    def lua_eval(self, code: str) -> dict:
        return _parse(_call(self.rc, "eval", code)) or {"ok": False}

    def inbox(self, since: int = 0) -> dict:
        data = _parse(_call(self.rc, "inbox", since))
        return data if isinstance(data, dict) else {"events": [], "last_seq": since}

    def blueprints(self) -> dict:
        data = _parse(_call(self.rc, "blueprints"))
        return data if isinstance(data, dict) else {"ok": False}

    def platforms(self) -> dict:
        data = _parse(_call(self.rc, "platforms"))
        return data if isinstance(data, dict) else {"ok": False}

    def build_blueprint(self, index: int, position: dict, direction: int | None = None,
                        mode: str = "ghost", timeout: float = 120) -> dict:
        params = {"kind": "build_blueprint", "index": index, "position": position, "mode": mode}
        if direction is not None:
            params["direction"] = direction
        result = self.submit(params)
        final = self.wait_job(result.get("id"), timeout=timeout)
        return {"submitted": result, "state": final.get("state"), "result": final.get("result")}

    def blueprint_create(self, name: str, x1: float, y1: float, x2: float, y2: float,
                         always_include_tiles: bool = False, include_entities: bool = True,
                         include_modules: bool = True, include_fuel: bool = True) -> dict:
        opts = {"x1": x1, "y1": y1, "x2": x2, "y2": y2,
                "always_include_tiles": always_include_tiles,
                "include_entities": include_entities,
                "include_modules": include_modules, "include_fuel": include_fuel}
        data = _parse(_call(self.rc, "blueprint_create", json.dumps(opts)))
        if not isinstance(data, dict) or not data.get("ok"):
            return data if isinstance(data, dict) else {"ok": False}
        encoded = data.pop("blueprint", None)
        if not encoded:
            return {"ok": False, "error": "empty blueprint"}
        BLUEPRINT_DIR.mkdir(parents=True, exist_ok=True)
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in name)[:80] or "blueprint"
        path = BLUEPRINT_DIR / f"{safe}.txt"
        path.write_text(encoded, encoding="utf-8")
        data.update({"name": safe, "path": str(path), "size": len(encoded)})
        return data

    def blueprint_build(self, name: str, x: float, y: float, direction: int = 0,
                        mode: str = "cost") -> dict:
        if name.endswith(".txt") or "/" in name or "\\" in name:
            path = Path(name)
        else:
            path = BLUEPRINT_DIR / f"{name}.txt"
        if not path.exists():
            return {"ok": False, "error": f"blueprint not found: {path}"}
        opts = {"x": x, "y": y, "direction": direction, "mode": mode,
                "string": path.read_text(encoding="utf-8")}
        data = _parse(_call(self.rc, "blueprint_build", json.dumps(opts)))
        return data if isinstance(data, dict) else {"ok": False}

    # -- detailed information / construction --------------------------------
    def detail(self, **opts: Any) -> dict:
        data = _parse(_call(self.rc, "detail", json.dumps(opts)))
        return data if isinstance(data, dict) else {"ok": False}

    def recipes(self, names: list[str] | None = None, filter: str | None = None,
                enabled_only: bool = False, limit: int = 300) -> dict:
        opts = {"enabled_only": enabled_only, "limit": limit}
        if names:
            opts["names"] = names
        if filter:
            opts["filter"] = filter
        data = _parse(_call(self.rc, "recipes", json.dumps(opts)))
        return data if isinstance(data, dict) else {"ok": False}

    def tech_tree(self, name: str | None = None, researched: bool | None = None,
                  enabled: bool | None = None, available_only: bool = False,
                  limit: int = 500) -> dict:
        opts: dict[str, Any] = {"available_only": available_only, "limit": limit}
        if name is not None:
            opts["name"] = name
        if researched is not None:
            opts["researched"] = researched
        if enabled is not None:
            opts["enabled"] = enabled
        data = _parse(_call(self.rc, "tech_tree", json.dumps(opts)))
        return data if isinstance(data, dict) else {"ok": False}

    def stats(self, items: list[str] | None = None) -> dict:
        if not items:
            items = [
                "iron-plate", "copper-plate", "steel-plate", "stone-brick", "coal",
                "iron-ore", "copper-ore", "electronic-circuit", "advanced-circuit",
                "processing-unit", "iron-gear-wheel", "copper-cable", "plastic-bar",
                "sulfur", "engine-unit", "electric-engine-unit",
                "automation-science-pack", "logistic-science-pack", "chemical-science-pack",
                "low-density-structure", "rocket-fuel", "rocket-part",
            ]
        data = _parse(_call(self.rc, "stats", json.dumps({"items": items})))
        return data if isinstance(data, dict) else {"ok": False}

    def alerts(self, limit: int = 100) -> dict:
        data = _parse(_call(self.rc, "alerts", json.dumps({"limit": limit})))
        return data if isinstance(data, dict) else {"ok": False}

    def wire_poles(self) -> dict:
        data = _parse(_call(self.rc, "wire", "{}"))
        return data if isinstance(data, dict) else {"ok": False}

    def set_recipe(self, unit_number: int, recipe: str | None) -> dict:
        data = _parse(_call(self.rc, "set_recipe", json.dumps({
            "unit_number": unit_number, "recipe": recipe})))
        return data if isinstance(data, dict) else {"ok": False}

    def build_entities(self, entities: list[dict], consume: bool = True,
                       wire_radius: float = 256) -> dict:
        data = _parse(_call(self.rc, "build_entities", json.dumps({
            "entities": entities, "consume": consume, "wire": True,
            "wire_radius": wire_radius})))
        return data if isinstance(data, dict) else {"ok": False}

    def resource_patches(self, radius: float = 256, limit: int = 40) -> dict:
        data = _parse(_call(self.rc, "resource_patches", json.dumps({
            "radius": radius, "limit": limit})))
        return data if isinstance(data, dict) else {"ok": False}

    def space(self, action: str, timeout: float = 120, **params) -> dict:
        action_obj = {"kind": "space", "action": action, **params}
        result = self.submit(action_obj)
        final = self.wait_job(result.get("id"), timeout=timeout)
        return {"submitted": result, "state": final.get("state"), "result": final.get("result")}

    # -- observation --------------------------------------------------------


    def observe(self, radius: float = 18) -> dict:
        return self.state(radius)

    def observe_text(self, radius: float = 18) -> str:
        return format_observation(self.state(radius))

    # -- LLM tools ----------------------------------------------------------

    def execute_tool(self, name: str, args: dict | None = None) -> str:
        """Execute one OpenAI-style tool call and return a JSON string."""
        args = args or {}
        try:
            if name == "observe":
                return format_observation(self.state(args.get("radius", 18)))
            if name == "walk_to":
                return json.dumps(self.perform("walk", x=args["x"], y=args["y"],
                                               timeout=args.get("timeout", 180)), ensure_ascii=False)
            if name == "mine":
                return json.dumps(self.perform("mine", name=args["resource"],
                                               count=args.get("count", 1),
                                               radius=args.get("radius", 64),
                                               timeout=args.get("timeout", 600)), ensure_ascii=False)
            if name == "craft":
                return json.dumps(self.perform("craft", recipe=args["recipe"],
                                               count=args.get("count", 1),
                                               timeout=args.get("timeout", 600)), ensure_ascii=False)
            if name == "place":
                params = {"name": args["entity"]}
                for k in ("x", "y", "direction", "recipe"):
                    if args.get(k) is not None:
                        params[k] = args[k]
                return json.dumps(self.perform("place", **params), ensure_ascii=False)
            if name == "insert_item":
                return json.dumps(self.perform("insert", item=args["item"],
                                               count=args.get("count", 1),
                                               target=args.get("target"),
                                               entity_name=args.get("entity_name"),
                                               **({"radius": args["radius"]} if "radius" in args else {})), ensure_ascii=False)
            if name == "take_item":
                return json.dumps(self.perform("take", item=args["item"],
                                               count=args.get("count", 1),
                                               target=args.get("target"),
                                               entity_name=args.get("entity_name"),
                                               **({"radius": args["radius"]} if "radius" in args else {})), ensure_ascii=False)
            if name == "rotate_entity":
                params = {"radius": args.get("radius", 12),
                          "reverse": bool(args.get("reverse", False))}
                for key in ("target", "entity_name"):
                    if args.get(key) is not None:
                        params[key] = args[key]
                return json.dumps(self.perform("rotate", **params), ensure_ascii=False)
            if name == "dismantle_entity":
                params = {"radius": args.get("radius", 12)}
                for key in ("target", "entity_name"):
                    if args.get(key) is not None:
                        params[key] = args[key]
                return json.dumps(self.perform("dismantle", **params), ensure_ascii=False)
            if name == "research":
                return json.dumps(self.perform("research", tech=args["tech"]), ensure_ascii=False)
            if name == "wait":
                return json.dumps(self.perform("wait", ticks=int(args.get("seconds", 1) * 60),
                                               timeout=args.get("seconds", 1) + 30), ensure_ascii=False)
            if name == "say":
                return json.dumps(self.perform("say", message=args.get("message", "")), ensure_ascii=False)
            if name == "find_water":
                return json.dumps(self.find_water(args.get("radius", 120)), ensure_ascii=False)
            if name == "nearby_entities":
                return json.dumps(self.nearby_entities(
                    radius=args.get("radius", 32),
                    name=args.get("name"),
                    entity_type=args.get("type"),
                    include_resources=bool(args.get("include_resources", False)),
                    include_nature=bool(args.get("include_nature", True)),
                    limit=args.get("limit", 50),
                ), ensure_ascii=False)
            if name == "scan":
                return json.dumps(self.scan(args.get("radius", 18)), ensure_ascii=False)
            if name == "recipe_info":
                return json.dumps(self.recipe(args["name"]), ensure_ascii=False)
            if name == "technologies":
                return json.dumps(self.techs(args.get("limit", 40)), ensure_ascii=False)
            if name == "cancel_all":
                return json.dumps(self.cancel_all(), ensure_ascii=False)
            if name == "save":
                return json.dumps(self.save(), ensure_ascii=False)
            if name == "respawn":
                return json.dumps(self.respawn(args.get("x"), args.get("y")), ensure_ascii=False)
            if name == "pause":
                return json.dumps(self.pause(True), ensure_ascii=False)
            if name == "resume":
                return json.dumps(self.resume(), ensure_ascii=False)
            if name == "build_blueprint":
                pos = {"x": args["x"], "y": args["y"]}
                return json.dumps(self.build_blueprint(args.get("index", 1), pos,
                                                       args.get("direction"),
                                                       mode=args.get("mode", "ghost"),
                                                       timeout=args.get("timeout", 120)), ensure_ascii=False)
            if name == "blueprint_create":
                return json.dumps(self.blueprint_create(args["name"], args["x1"], args["y1"],
                                                       args["x2"], args["y2"],
                                                       args.get("always_include_tiles", False),
                                                       args.get("include_entities", True),
                                                       args.get("include_modules", True),
                                                       args.get("include_fuel", True)), ensure_ascii=False)
            if name == "blueprint_build":
                return json.dumps(self.blueprint_build(args["name"], args["x"], args["y"],
                                                       args.get("direction", 0),
                                                       args.get("mode", "cost")), ensure_ascii=False)
            if name == "space":
                params = {k: args[k] for k in ("platform", "planet", "starter_pack", "name", "quality",
                                               "station", "temporary", "wait_conditions", "apply") if k in args}
                return json.dumps(self.space(args["action"], timeout=args.get("timeout", 120), **params), ensure_ascii=False)
            if name == "entity_detail":
                opts = {k: args[k] for k in ("unit_number", "position", "radius", "name", "type", "limit") if k in args}
                return json.dumps(self.detail(**opts), ensure_ascii=False)
            if name == "recipes_query":
                return json.dumps(self.recipes(names=args.get("names"),
                                               filter=args.get("filter"),
                                               enabled_only=args.get("enabled_only", False),
                                               limit=args.get("limit", 300)), ensure_ascii=False)
            if name == "tech_tree":
                return json.dumps(self.tech_tree(name=args.get("name"),
                                                 researched=args.get("researched"),
                                                 enabled=args.get("enabled"),
                                                 available_only=bool(args.get("available_only", False)),
                                                 limit=args.get("limit", 500)), ensure_ascii=False)
            if name == "production_stats":
                return json.dumps(self.stats(args.get("items")), ensure_ascii=False)
            if name == "alerts":
                return json.dumps(self.alerts(args.get("limit", 100)), ensure_ascii=False)
            if name == "wire_poles":
                return json.dumps(self.wire_poles(), ensure_ascii=False)
            if name == "set_recipe":
                return json.dumps(self.set_recipe(int(args["unit_number"]), args.get("recipe")),
                                  ensure_ascii=False)
            if name == "build_entities":
                return json.dumps(self.build_entities(args["entities"],
                                                      consume=args.get("consume", True),
                                                      wire_radius=args.get("wire_radius", 256)),
                                  ensure_ascii=False)
            if name == "resource_patches":
                return json.dumps(self.resource_patches(args.get("radius", 256),
                                                        args.get("limit", 40)), ensure_ascii=False)
            if name == "lua_eval":
                return json.dumps(self.lua_eval(args["code"]), ensure_ascii=False)
            return json.dumps({"ok": False, "error": f"unknown tool {name}"})
        except Exception as e:  # keep the loop alive: the LLM gets the error
            return json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}, ensure_ascii=False)


def format_observation(state: dict) -> str:
    """Compact text view for an LLM (JSON stays available via state())."""
    ch = state.get("character") or {}
    lines: list[str] = []
    tick = state.get("tick")
    pos = ch.get("position") or {}
    player = state.get("player") or {}
    if player.get("connected"):
        lines.append(f"Real player {player.get('name')} (#{player.get('index')}) connected on {player.get('physical_surface')} | "
                     f"character ({pos.get('x')}, {pos.get('y')}) hp {ch.get('health')}/{ch.get('max_health')}")
    else:
        lines.append(f"Bot player not connected (waiting for {state.get('bot_name', 'LLM-Bot')}) | "
                     f"character ({pos.get('x')}, {pos.get('y')}) hp {ch.get('health')}/{ch.get('max_health')}")
    inv = ch.get("inventory") or []
    lines.append("Inventory: " + (", ".join(f"{i['name']} x{i['count']}" for i in inv) if inv else "empty"))
    cq = ch.get("crafting_queue") or []
    lines.append("Crafting: " + (", ".join(f"{q['recipe']} x{q['count']}" for q in cq) if cq else "none"))
    res = state.get("resources") or []
    if res:
        lines.append("Resources nearby: " + ", ".join(
            f"{r['name']} @({r['nearest']['x']},{r['nearest']['y']}) "
            f"d={round(r['nearest']['distance'], 1)} tiles={r.get('tiles')} total={r.get('total_amount')}"
            for r in res[:8]))
    ents = state.get("entities") or []
    if ents:
        lines.append("Entities nearby: " + ", ".join(
            f"{e['name']}#{e.get('unit_number')} @({e['x']},{e['y']}) d={round(e['distance'], 1)}"
            for e in ents[:12]))
    job = state.get("job")
    if job:
        lines.append(f"Current job: {job['kind']} phase={job['phase']} detail={job.get('detail')}")
    else:
        lines.append("Current job: idle")
    queue = state.get("queue") or []
    if queue:
        lines.append("Queued: " + ", ".join(f"{q['kind']}#{q['id']}" for q in queue))
    force = state.get("force") or {}
    lines.append(f"Research: {force.get('current_research')} {round(100 * float(force.get('research_progress') or 0), 1)}%")
    return "\n".join(lines)


# OpenAI-compatible tool schemas -------------------------------------------------

TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "observe", "description": "Look at the character, inventory, nearby resources/entities and current job.",
        "parameters": {"type": "object", "properties": {"radius": {"type": "number", "default": 18}}},
    }},
    {"type": "function", "function": {
        "name": "walk_to", "description": "Walk to a map position with collision-aware pathfinding.",
        "parameters": {"type": "object", "properties": {
            "x": {"type": "number"}, "y": {"type": "number"}}, "required": ["x", "y"]},
    }},
    {"type": "function", "function": {
        "name": "mine", "description": "Walk to and mine a solid resource (iron-ore, copper-ore, coal, stone, uranium-ore), or use resource='tree' to chop trees for wood.",
        "parameters": {"type": "object", "properties": {
            "resource": {"type": "string"}, "count": {"type": "integer", "default": 1},
            "radius": {"type": "number", "default": 64}}, "required": ["resource"]},
    }},
    {"type": "function", "function": {
        "name": "craft", "description": "Hand-craft a recipe if the character has the ingredients.",
        "parameters": {"type": "object", "properties": {
            "recipe": {"type": "string"}, "count": {"type": "integer", "default": 1}}, "required": ["recipe"]},
    }},
    {"type": "function", "function": {
        "name": "place", "description": "Place an entity from the character's inventory. Consumes one item and checks collisions.",
        "parameters": {"type": "object", "properties": {
            "entity": {"type": "string"}, "x": {"type": "number"}, "y": {"type": "number"},
            "direction": {"type": "integer", "description": "Factorio direction: 0 N, 4 E, 8 S, 12 W (diagonals 2/6/10/14)"},
            "recipe": {"type": "string"}}, "required": ["entity"]},
    }},
    {"type": "function", "function": {
        "name": "rotate_entity",
        "description": "Rotate an already placed building 90 degrees as the real player. Target by unit_number (target) or nearest entity_name; must be within 10 tiles. Use place(direction) to choose rotation at build time.",
        "parameters": {"type": "object", "properties": {
            "target": {"type": "integer"}, "entity_name": {"type": "string"},
            "radius": {"type": "number", "default": 12},
            "reverse": {"type": "boolean", "default": False}},
            "required": []},
    }},
    {"type": "function", "function": {
        "name": "dismantle_entity",
        "description": "Dismantle/mine an already placed building as the real player, returning its items; target by unit_number (target) or nearest entity_name and walk within 10 tiles first.",
        "parameters": {"type": "object", "properties": {
            "target": {"type": "integer"}, "entity_name": {"type": "string"},
            "radius": {"type": "number", "default": 12}},
            "required": []},
    }},
    {"type": "function", "function": {
        "name": "insert_item", "description": "Move items from the character into a nearby entity (e.g. furnace/chest).",
        "parameters": {"type": "object", "properties": {
            "item": {"type": "string"}, "count": {"type": "integer", "default": 1},
            "target": {"type": "integer", "description": "unit_number; omit to use entity_name"},
            "entity_name": {"type": "string"}, "radius": {"type": "number", "default": 12}},
            "required": ["item"]},
    }},
    {"type": "function", "function": {
        "name": "take_item", "description": "Move items from a nearby entity into the character.",
        "parameters": {"type": "object", "properties": {
            "item": {"type": "string"}, "count": {"type": "integer", "default": 1},
            "target": {"type": "integer"}, "entity_name": {"type": "string"},
            "radius": {"type": "number", "default": 12}}, "required": ["item"]},
    }},
    {"type": "function", "function": {
        "name": "research", "description": "Queue a technology at the force's research queue.",
        "parameters": {"type": "object", "properties": {"tech": {"type": "string"}}, "required": ["tech"]},
    }},
    {"type": "function", "function": {
        "name": "scan", "description": "Scan nearby resources and entities with a larger radius.",
        "parameters": {"type": "object", "properties": {"radius": {"type": "number", "default": 32}}},
    }},
    {"type": "function", "function": {
        "name": "nearby_entities",
        "description": "List entities near the player as a filtered, distance-sorted table. Use include_nature=false to hide trees/fish/decoratives, or filter by name/type (e.g. type='furnace', name='lab'). Resources can be included with include_resources=true.",
        "parameters": {"type": "object", "properties": {
            "radius": {"type": "number", "default": 32},
            "name": {"type": "string"},
            "type": {"type": "string"},
            "include_resources": {"type": "boolean", "default": False},
            "include_nature": {"type": "boolean", "default": True},
            "limit": {"type": "integer", "default": 50}}},
    }},
    {"type": "function", "function": {
        "name": "find_water",
        "description": "Find the nearest water within radius and a valid offshore-pump position plus a nearby shore/walk position. If the spawn area is inland, retry with radius 120+.",
        "parameters": {"type": "object", "properties": {"radius": {"type": "number", "default": 120}}},
    }},
    {"type": "function", "function": {
        "name": "recipe_info", "description": "Get ingredients/products of a recipe.",
        "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
    }},
    {"type": "function", "function": {
        "name": "technologies", "description": "List enabled, unresearched technologies.",
        "parameters": {"type": "object", "properties": {"limit": {"type": "integer", "default": 40}}},
    }},
    {"type": "function", "function": {
        "name": "wait", "description": "Wait in game seconds (real time at speed 1).",
        "parameters": {"type": "object", "properties": {"seconds": {"type": "number", "default": 1}}},
    }},
    {"type": "function", "function": {
        "name": "say", "description": "Send a chat message visible to connected players.",
        "parameters": {"type": "object", "properties": {"message": {"type": "string"}}},
    }},
    {"type": "function", "function": {
        "name": "cancel_all", "description": "Stop the current job and clear the queue.",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "save", "description": "Ask the server to save the current map.",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "respawn", "description": "Respawn the character (loses inventory). Omit x/y to use the stored spawn point.",
        "parameters": {"type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}}},
    }},
    {"type": "function", "function": {
        "name": "build_blueprint",
        "description": "Build one of the player's blueprint-library records. mode=ghost places construction ghosts; mode=cost instantly builds and consumes matching items from the player inventory; mode=force instantly builds without consuming items.",
        "parameters": {"type": "object", "properties": {
            "index": {"type": "integer", "default": 1}, "x": {"type": "number"}, "y": {"type": "number"},
            "direction": {"type": "integer"},
            "mode": {"type": "string", "enum": ["ghost", "cost", "force"], "default": "ghost"}},
            "required": ["x", "y"]},
    }},
    {"type": "function", "function": {
        "name": "lua_eval",
        "description": "Advanced: run Lua in the scenario after the operator enables eval. Use only for normal-player APIs not covered by other tools; never create items/teleport/cheat.",
        "parameters": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]},
    }},
    {"type": "function", "function": {
        "name": "blueprint_create",
        "description": "Create a blueprint string from the player's current surface area and save it locally.",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string"}, "x1": {"type": "number"}, "y1": {"type": "number"},
            "x2": {"type": "number"}, "y2": {"type": "number"},
            "always_include_tiles": {"type": "boolean", "default": False},
            "include_entities": {"type": "boolean", "default": True}},
            "required": ["name", "x1", "y1", "x2", "y2"]},
    }},
    {"type": "function", "function": {
        "name": "blueprint_build",
        "description": "Build a saved blueprint string at a map position. mode=cost instantly builds and consumes the player's items (default); mode=force instantly builds without items; mode=ghost only places construction ghosts.",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string"}, "x": {"type": "number"}, "y": {"type": "number"},
            "direction": {"type": "integer", "default": 0},
            "mode": {"type": "string", "enum": ["cost", "force", "ghost"], "default": "cost"}},
            "required": ["name", "x", "y"]},
    }},
    {"type": "function", "function": {
        "name": "space",
        "description": "Space Age platform actions: create (applies the starter pack by default), apply_starter_pack, enter, leave, land, pause, resume, schedule, go, add_stop, clear_schedule, hub. Use observe for platform and planet names.",
        "parameters": {"type": "object", "properties": {
            "action": {"type": "string", "enum": ["enter", "leave", "land", "create", "apply_starter_pack", "pause", "resume", "schedule", "go", "add_stop", "clear_schedule", "hub"]},
            "platform": {"type": "string"}, "planet": {"type": "string"},
            "starter_pack": {"type": "string"}, "name": {"type": "string"},
            "quality": {"type": "string", "default": "normal"},
            "station": {"type": "string"}, "temporary": {"type": "boolean"},
            "apply": {"type": "boolean", "default": True}},
            "required": ["action"]},
    }},
    {"type": "function", "function": {
        "name": "entity_detail",
        "description": "Detailed entity info: direction, status name, health, minable, recipe, all inventories, fluids, electric network, drop/mining positions, inserter filter and belt contents. Target by unit_number, or scan by position/radius/name/type.",
        "parameters": {"type": "object", "properties": {
            "unit_number": {"type": "integer"},
            "position": {"type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}}},
            "radius": {"type": "number", "default": 16},
            "name": {"type": "string"}, "type": {"type": "string"},
            "limit": {"type": "integer", "default": 50}}},
    }},
    {"type": "function", "function": {
        "name": "recipes_query",
        "description": "Bulk recipe database query. Filter by substring or explicit names; returns energy, categories, ingredients and products for enabled recipes.",
        "parameters": {"type": "object", "properties": {
            "names": {"type": "array", "items": {"type": "string"}},
            "filter": {"type": "string"},
            "enabled_only": {"type": "boolean", "default": False},
            "limit": {"type": "integer", "default": 300}}},
    }},
    {"type": "function", "function": {
        "name": "tech_tree",
        "description": "Full technology tree with researched/enabled state, prerequisites, unmet prerequisites, cost/count, science ingredients and trigger info.",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string"},
            "researched": {"type": "boolean"},
            "enabled": {"type": "boolean"},
            "available_only": {"type": "boolean", "default": False},
            "limit": {"type": "integer", "default": 500}}},
    }},
    {"type": "function", "function": {
        "name": "production_stats",
        "description": "Force item production statistics (produced/consumed counters) for item names only; fluids such as sulfuric-acid are not valid here. Omit items for a safe default list.",
        "parameters": {"type": "object", "properties": {
            "items": {"type": "array", "items": {"type": "string"}}}},
    }},
    {"type": "function", "function": {
        "name": "alerts",
        "description": "List buildings with problems: no power/fuel/ingredients/recipe, full output, fluid shortage, no resources, disconnected.",
        "parameters": {"type": "object", "properties": {
            "limit": {"type": "integer", "default": 100}}},
    }},
    {"type": "function", "function": {
        "name": "wire_poles",
        "description": "Connect nearby electric poles with copper wire (repairs blueprint-built pole networks).",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "set_recipe",
        "description": "Set or clear the recipe of an existing assembling machine by unit_number (refinery/chemical plant included). Stone furnaces have a fixed recipe and reject this tool. The recipe must be enabled.",
        "parameters": {"type": "object", "properties": {
            "unit_number": {"type": "integer"},
            "recipe": {"type": "string"}},
            "required": ["unit_number"]},
    }},
    {"type": "function", "function": {
        "name": "build_entities",
        "description": "Batch construction service: place a list of entities at exact positions, consuming the matching items from the real player inventory. Recipes are set after building; poles are auto-wired. Use this for factories instead of hundreds of single place calls.",
        "parameters": {"type": "object", "properties": {
            "entities": {"type": "array", "items": {"type": "object", "properties": {
                "name": {"type": "string"}, "x": {"type": "number"}, "y": {"type": "number"},
                "direction": {"type": "integer"}, "recipe": {"type": "string"}}}},
            "consume": {"type": "boolean", "default": True},
            "wire_radius": {"type": "number", "default": 256}},
            "required": ["entities"]},
    }},
    {"type": "function", "function": {
        "name": "resource_patches",
        "description": "Cluster resource tiles into patches within a radius: amount, tile count, centre and bounding box. Useful for choosing mining outposts/oil routes.",
        "parameters": {"type": "object", "properties": {
            "radius": {"type": "number", "default": 256},
            "limit": {"type": "integer", "default": 40}}},
    }},
]
