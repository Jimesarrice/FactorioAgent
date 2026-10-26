"""stdio MCP server exposing the Factorio embodied agent to external LLM clients.

The server connects to the same RCON/scenario control plane used by the built-in
bot loop.  It can auto-read host/port/password from ``state/webui.json`` so an
MCP client launched with this project's working directory connects to the active
server without extra configuration.

Run:
    python -m bridge.mcp_server
    python -m bridge.mcp_server --port 27017 --password test

MCP client config: see ``docs/mcp-config.example.json`` and ``docs/MCP.md``.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from .agent import AgentBridge, TOOL_SCHEMAS


# Tools that are not part of the OpenAI tool set but are useful to an external
# MCP agent (state inspection, console inbox, lifecycle and raw job control).
MCP_EXTRA_TOOLS: list[dict] = [
    {"type": "function", "function": {
        "name": "get_state",
        "description": "Return the full game state JSON (character, player, inventory, force, nearby resources/entities, job/queue).",
        "parameters": {"type": "object", "properties": {
            "radius": {"type": "number", "default": 18}}},
    }},
    {"type": "function", "function": {
        "name": "decision_context",
        "description": "One-call decision context: state + console inbox + job events + blueprint library + space platforms.",
        "parameters": {"type": "object", "properties": {
            "radius": {"type": "number", "default": 18},
            "inbox_since": {"type": "integer", "default": 0},
            "event_since": {"type": "integer", "default": 0},
            "limit": {"type": "integer", "default": 60}}},
    }},
    {"type": "function", "function": {
        "name": "get_inbox",
        "description": "Read console/chat instructions received by the scenario since a sequence number.",
        "parameters": {"type": "object", "properties": {
            "since": {"type": "integer", "default": 0}}},
    }},
    {"type": "function", "function": {
        "name": "clear_inbox",
        "description": "Clear the scenario console inbox.",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "instruct",
        "description": "Send an operator instruction to the scenario inbox (visible to the in-game agent).",
        "parameters": {"type": "object", "properties": {
            "text": {"type": "string"},
            "player_index": {"type": "integer"}}, "required": ["text"]},
    }},
    {"type": "function", "function": {
        "name": "get_events",
        "description": "Read the scenario job/event journal since a sequence number.",
        "parameters": {"type": "object", "properties": {
            "since": {"type": "integer", "default": 0}}},
    }},
    {"type": "function", "function": {
        "name": "get_blueprints",
        "description": "List the real player's blueprint-library records.",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "get_platforms",
        "description": "List Space Age platforms, hubs and planet/space locations.",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "ping",
        "description": "Ping the scenario and return the current game tick.",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "pause",
        "description": "Pause the game simulation.",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "resume",
        "description": "Resume the game simulation.",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "set_speed",
        "description": "Set game speed multiplier (0.01 .. 100). Useful for long autonomous tests.",
        "parameters": {"type": "object", "properties": {
            "value": {"type": "number", "default": 1}}, "required": ["value"]},
    }},
    {"type": "function", "function": {
        "name": "wait_idle",
        "description": "Wait until the current job and queue are empty, then return the latest state.",
        "parameters": {"type": "object", "properties": {
            "timeout": {"type": "number", "default": 180}}},
    }},
    {"type": "function", "function": {
        "name": "submit_job",
        "description": "Advanced: submit a raw scenario job (walk/mine/craft/place/insert/take/research/wait/say/build_blueprint/space). Returns the job id; set wait=true to block.",
        "parameters": {"type": "object", "properties": {
            "job": {"type": "object"}, "wait": {"type": "boolean", "default": False},
            "timeout": {"type": "number", "default": 180}}, "required": ["job"]},
    }},
    {"type": "function", "function": {
        "name": "wait_job",
        "description": "Wait for a submitted job id and return its final state/result.",
        "parameters": {"type": "object", "properties": {
            "id": {"type": "integer"}, "timeout": {"type": "number", "default": 180}},
            "required": ["id"]},
    }},
    {"type": "function", "function": {
        "name": "cancel_job",
        "description": "Cancel one queued/running job by id. Omit id to cancel the current job (see cancel_all for the queue).",
        "parameters": {"type": "object", "properties": {
            "id": {"type": "integer"}}},
    }},
    {"type": "function", "function": {
        "name": "set_bot_name",
        "description": "Operator-only: bind the scenario to a different real player name.",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string"}}, "required": ["name"]},
    }},
    {"type": "function", "function": {
        "name": "set_bare",
        "description": "Lab-only fallback: allow controlling a bare character when no real client is connected. Not part of normal play.",
        "parameters": {"type": "object", "properties": {
            "enabled": {"type": "boolean"}}, "required": ["enabled"]},
    }},
    {"type": "function", "function": {
        "name": "set_eval",
        "description": "Operator-only: enable/disable the lua_eval escape hatch. Enabling it allows arbitrary Lua and bypasses normal player constraints.",
        "parameters": {"type": "object", "properties": {
            "enabled": {"type": "boolean"}}, "required": ["enabled"]},
    }},
]


def _connection_defaults() -> dict:
    """Read the same local config used by the Web UI, if available."""
    try:
        from .settings import load_config
        b = load_config().get("bot", {})
    except Exception:
        b = {}
    return {
        "host": os.environ.get("FACTORIO_HOST") or b.get("host", "127.0.0.1"),
        "port": int(os.environ.get("FACTORIO_RCON_PORT") or b.get("rcon_port", 27016)),
        "password": os.environ.get("FACTORIO_RCON_PASSWORD") or b.get("rcon_password", "test"),
    }


class McpServer:
    def __init__(self, host: str | None = None, port: int | None = None,
                 password: str | None = None):
        defaults = _connection_defaults()
        self.host = host or defaults["host"]
        self.port = int(port if port is not None else defaults["port"])
        self.password = password if password is not None else defaults["password"]
        self.bridge: AgentBridge | None = None

    def bridge_or_connect(self) -> AgentBridge:
        if self.bridge is None:
            self.bridge = AgentBridge(self.host, self.port, self.password)
        return self.bridge

    def reset(self) -> None:
        if self.bridge:
            try:
                self.bridge.close()
            except Exception:
                pass
            self.bridge = None

    def call(self, name: str, args: dict) -> Any:
        bridge = self.bridge_or_connect()
        try:
            return self._dispatch(bridge, name, args)
        except Exception:
            # A dropped RCON connection should not kill the MCP session.
            self.reset()
            bridge = self.bridge_or_connect()
            return self._dispatch(bridge, name, args)

    def _dispatch(self, bridge: AgentBridge, name: str, args: dict) -> Any:
        args = args or {}
        if name == "get_state":
            return json.dumps({"ok": True, "state": bridge.state(args.get("radius", 18))},
                              ensure_ascii=False)
        if name == "decision_context":
            limit = max(1, int(args.get("limit", 60)))
            state = bridge.state(args.get("radius", 18))
            inbox = bridge.inbox(args.get("inbox_since", 0))
            events = bridge.events(args.get("event_since", 0))
            if isinstance(events, dict) and isinstance(events.get("events"), list):
                events["events"] = events["events"][-limit:]
            return json.dumps({
                "ok": True,
                "state": state,
                "inbox": inbox,
                "events": events,
                "blueprints": bridge.blueprints(),
                "platforms": bridge.platforms(),
            }, ensure_ascii=False)
        if name == "get_inbox":
            return json.dumps(bridge.inbox(args.get("since", 0)), ensure_ascii=False)
        if name == "clear_inbox":
            return json.dumps(bridge.clear_inbox(), ensure_ascii=False)
        if name == "instruct":
            if "player_index" in args and args["player_index"] is not None:
                return json.dumps(bridge.instruct(args["text"], args["player_index"]),
                                  ensure_ascii=False)
            return json.dumps(bridge.instruct(args["text"]), ensure_ascii=False)
        if name == "get_events":
            return json.dumps(bridge.events(args.get("since", 0)), ensure_ascii=False)
        if name == "get_blueprints":
            return json.dumps(bridge.blueprints(), ensure_ascii=False)
        if name == "get_platforms":
            return json.dumps(bridge.platforms(), ensure_ascii=False)
        if name == "ping":
            return bridge.rc.execute('/c remote.call("agentbridge", "ping")')
        if name == "pause":
            return json.dumps(bridge.pause(True), ensure_ascii=False)
        if name == "resume":
            return json.dumps(bridge.pause(False), ensure_ascii=False)
        if name == "set_speed":
            return json.dumps(bridge.speed(float(args.get("value", 1))), ensure_ascii=False)
        if name == "wait_idle":
            final = bridge.wait_idle(timeout=float(args.get("timeout", 180)))
            return json.dumps(final, ensure_ascii=False)
        if name == "submit_job":
            job = args.get("job")
            if not isinstance(job, dict) or not job.get("kind"):
                return json.dumps({"ok": False, "error": "job object with kind is required"},
                                  ensure_ascii=False)
            result = bridge.submit(job)
            if args.get("wait") and result.get("id"):
                final = bridge.wait_job(result["id"], timeout=float(args.get("timeout", 180)))
                return json.dumps({"ok": True, "submitted": result, "final": final},
                                  ensure_ascii=False)
            return json.dumps({"ok": True, "submitted": result}, ensure_ascii=False)
        if name == "wait_job":
            final = bridge.wait_job(int(args["id"]), timeout=float(args.get("timeout", 180)))
            return json.dumps(final, ensure_ascii=False)
        if name == "cancel_job":
            return json.dumps(bridge.cancel(args.get("id")), ensure_ascii=False)
        if name == "set_bot_name":
            return json.dumps(bridge.set_bot_name(str(args["name"])), ensure_ascii=False)
        if name == "set_bare":
            return json.dumps(bridge.set_bare(bool(args.get("enabled"))), ensure_ascii=False)
        if name == "set_eval":
            return json.dumps(bridge.set_eval(bool(args.get("enabled"))), ensure_ascii=False)
        return bridge.execute_tool(name, args)

    def handle(self, msg: dict) -> dict | None:
        method = msg.get("method")
        msg_id = msg.get("id")
        if method == "initialize":
            return {"jsonrpc": "2.0", "id": msg_id, "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "factorio-agentbridge", "version": "0.3.9"},
                "instructions": (
                    "You are connected to a real Factorio 2.1 server through an embodied "
                    "agent. Call decision_context first, then use one blocking tool at a "
                    "time. Use observe/scan/get_state for facts, walk_to/mine/craft/place/"
                    "insert_item/take_item/research for normal play, blueprint_create/"
                    "blueprint_build for structures, space for Space Age, and say to report. "
                    "Never invent coordinates or claim success without ok/done. lua_eval is "
                    "disabled unless the operator enables it."
                ),
            }}
        if method in ("notifications/initialized", "initialized"):
            return None
        if method == "ping":
            return {"jsonrpc": "2.0", "id": msg_id, "result": {}}
        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": _tools()}}
        if method == "tools/call":
            params = msg.get("params") or {}
            name = params.get("name", "")
            args = params.get("arguments") or {}
            try:
                text = self.call(name, args)
                return {"jsonrpc": "2.0", "id": msg_id, "result": {
                    "content": [{"type": "text", "text": str(text)}],
                    "isError": False,
                }}
            except Exception as e:
                return {"jsonrpc": "2.0", "id": msg_id, "result": {
                    "content": [{"type": "text",
                                 "text": f"{type(e).__name__}: {e} (is the Factorio server running and RCON reachable?)"}],
                    "isError": True,
                }}
        if method in ("shutdown", "exit"):
            return {"jsonrpc": "2.0", "id": msg_id, "result": {}}
        if msg_id is None:
            return None
        return {"jsonrpc": "2.0", "id": msg_id,
                "error": {"code": -32601, "message": f"method not found: {method}"}}


def _tools() -> list[dict]:
    tools = []
    for schema in TOOL_SCHEMAS + MCP_EXTRA_TOOLS:
        fn = schema["function"]
        tools.append({
            "name": fn["name"],
            "description": fn.get("description", ""),
            "inputSchema": fn.get("parameters", {"type": "object", "properties": {}}),
        })
    return tools


def _read_message(stream) -> dict | None:
    """Read newline-delimited JSON, also tolerating LSP-style headers."""
    headers: dict[str, str] = {}
    while True:
        line = stream.readline()
        if not line:
            return None
        if line.strip() == b"":
            continue
        if b":" in line and not line.lstrip().startswith(b"{"):
            key, _, value = line.decode("ascii", "replace").partition(":")
            headers[key.strip().lower()] = value.strip()
            if "content-length" in headers:
                while True:
                    blank = stream.readline()
                    if blank in (b"\n", b"\r\n", b""):
                        break
                length = int(headers["content-length"])
                data = stream.read(length)
                return json.loads(data.decode("utf-8"))
            continue
        return json.loads(line.decode("utf-8"))


def main():
    # MCP stdio is UTF-8 regardless of the Windows locale (tool results may
    # contain Chinese text from the scenario/logs).
    try:
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
        sys.stderr.reconfigure(encoding="utf-8", newline="\n")
    except Exception:
        pass
    defaults = _connection_defaults()
    ap = argparse.ArgumentParser(description="Factorio embodied-agent MCP server")
    ap.add_argument("--host", default=defaults["host"])
    ap.add_argument("--port", type=int, default=defaults["port"])
    ap.add_argument("--password", default=defaults["password"])
    a = ap.parse_args()

    server = McpServer(a.host, a.port, a.password)
    out = sys.stdout
    print(f"[mcp] factorio agentbridge on {a.host}:{a.port}", file=sys.stderr, flush=True)
    while True:
        try:
            msg = _read_message(sys.stdin.buffer)
        except Exception as e:
            print(f"[mcp] read error: {e}", file=sys.stderr)
            break
        if msg is None:
            break
        try:
            response = server.handle(msg)
        except Exception as e:
            print(f"[mcp] handler error: {e}", file=sys.stderr)
            response = {"jsonrpc": "2.0", "id": msg.get("id"),
                        "error": {"code": -32603, "message": str(e)}}
        if response is not None:
            out.write(json.dumps(response, ensure_ascii=False) + "\n")
            out.flush()
    server.reset()


if __name__ == "__main__":
    main()
