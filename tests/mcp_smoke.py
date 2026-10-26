"""Smoke-test the stdio MCP server against this project.

Usage:
    python tests/mcp_smoke.py             # protocol/tools/list only
    python tests/mcp_smoke.py --live      # also call read-only tools (server required)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "observe", "walk_to", "mine", "craft", "place", "insert_item", "take_item", "rotate_entity", "dismantle_entity",
    "research", "scan", "nearby_entities", "find_water", "recipe_info", "technologies", "wait",
    "say", "cancel_all", "save", "respawn", "build_blueprint", "lua_eval",
    "blueprint_create", "blueprint_build", "space", "get_state",
    "decision_context", "get_inbox", "clear_inbox", "instruct", "get_events",
    "get_blueprints", "get_platforms", "ping", "pause", "resume", "set_speed",
    "submit_job", "wait_job", "wait_idle", "cancel_job", "set_bot_name", "set_bare", "set_eval",
    "entity_detail", "recipes_query", "tech_tree", "production_stats", "alerts",
    "wire_poles", "set_recipe", "build_entities", "resource_patches",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--timeout", type=float, default=30)
    args = ap.parse_args()

    proc = subprocess.Popen(
        [sys.executable, "-m", "bridge.mcp_server"],
        cwd=str(ROOT), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1,
    )

    def rpc(msg: dict) -> dict:
        assert proc.stdin is not None and proc.stdout is not None
        proc.stdin.write(json.dumps(msg, ensure_ascii=False) + "\n")
        proc.stdin.flush()
        line = proc.stdout.readline()
        if not line:
            err = proc.stderr.read() if proc.stderr else ""
            raise RuntimeError(f"MCP server closed: {err[:1000]}")
        return json.loads(line)

    def tool(name: str, payload: dict | None = None) -> tuple[bool, str]:
        data = rpc({"jsonrpc": "2.0", "id": name, "method": "tools/call",
                    "params": {"name": name, "arguments": payload or {}}})
        result = data.get("result") or {}
        text = (result.get("content") or [{}])[0].get("text", "")
        return bool(result.get("isError")), text

    try:
        init = rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                               "clientInfo": {"name": "mcp-smoke", "version": "1"}}})
        info = init["result"]["serverInfo"]
        tools = rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]
        names = {t["name"] for t in tools}
        missing = sorted(EXPECTED - names)
        if missing:
            print("FAIL missing tools:", missing)
            return 1
        print(f"PASS initialize {info['name']} {info['version']}; tools={len(tools)}")

        if args.live:
            for name, arguments in (
                ("ping", {}),
                ("get_state", {"radius": 10}),
                ("decision_context", {"radius": 10, "limit": 5}),
                ("observe", {"radius": 10}),
                ("nearby_entities", {"radius": 20, "include_nature": False}),
                ("find_water", {"radius": 120}),
                ("recipe_info", {"name": "lab"}),
                ("technologies", {"limit": 5}),
                ("entity_detail", {"radius": 12, "limit": 3}),
                ("recipes_query", {"names": ["electronic-circuit"], "enabled_only": False}),
                ("tech_tree", {"name": "landfill"}),
                ("production_stats", {}),
                ("alerts", {"limit": 5}),
                ("resource_patches", {"radius": 80, "limit": 3}),
                ("wire_poles", {}),
                ("get_blueprints", {}),
                ("get_platforms", {}),
            ):
                is_error, text = tool(name, arguments)
                if is_error:
                    print(f"FAIL {name}: {text[:400]}")
                    return 1
                print(f"PASS {name}: {text[:120].replace(chr(10), ' ')}")
        print("ALL PASS")
        return 0
    finally:
        try:
            if proc.stdin:
                proc.stdin.close()
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
