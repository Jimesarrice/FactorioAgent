"""Smoke-test the input-only client MCP server.

Usage:
  python tests/client_mcp_smoke.py          # protocol/tools/list only
  python tests/client_mcp_smoke.py --live   # attach/focus/screenshot a running client
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "client_list_windows", "client_attach", "client_info", "client_focus",
    "client_screenshot", "client_key", "client_hold", "client_walk",
    "client_click", "client_scroll", "client_type", "client_map", "client_inventory",
    "client_memory_attach", "client_memory_status", "client_memory_observe",
    "client_memory_inventory", "client_memory_detach",
    "client_input_attach", "client_input_status", "client_input_key",
    "client_input_walk", "client_input_text", "client_input_move",
    "client_input_click", "client_input_world_click", "client_input_mouse_off",
    "client_input_detach",
    "client_action_attach", "client_action_state", "client_action_mine",
    "client_action_pick", "client_action_build", "client_action_open",
    "client_action_walk_to", "client_action_stop", "client_action_close_ui",
    "client_action_status", "client_action_detach",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--memory", action="store_true", help="also attach/read the Frida memory bridge")
    ap.add_argument("--background", action="store_true", help="also attach the background SDL input channel")
    ap.add_argument("--actions", action="store_true", help="also attach the high-level background action agent")
    ap.add_argument("--player-name", help="bot player name when the server has multiple players")
    args = ap.parse_args()
    proc = subprocess.Popen(
        [sys.executable, "-m", "bridge.client_mcp_server"],
        cwd=str(ROOT), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1,
    )

    def rpc(msg: dict) -> dict:
        assert proc.stdin and proc.stdout
        proc.stdin.write(json.dumps(msg, ensure_ascii=False) + "\n")
        proc.stdin.flush()
        line = proc.stdout.readline()
        if not line:
            err = proc.stderr.read() if proc.stderr else ""
            raise RuntimeError(f"client MCP closed: {err[:500]}")
        return json.loads(line)

    def tool(name: str, arguments: dict | None = None) -> tuple[bool, str]:
        data = rpc({"jsonrpc": "2.0", "id": name, "method": "tools/call",
                    "params": {"name": name, "arguments": arguments or {}}})
        result = data.get("result") or {}
        return bool(result.get("isError")), (result.get("content") or [{}])[0].get("text", "")

    try:
        init = rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                               "clientInfo": {"name": "client-smoke", "version": "1"}}})
        info = init["result"]["serverInfo"]
        tools = rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]
        names = {t["name"] for t in tools}
        missing = sorted(EXPECTED - names)
        if missing:
            print("FAIL missing tools:", missing)
            return 1
        print(f"PASS initialize {info['name']} {info['version']}; tools={len(tools)}")
        if args.live:
            is_error, text = tool("client_list_windows", {})
            if is_error:
                print("FAIL client_list_windows:", text[:300])
                return 1
            windows = json.loads(text)
            print(f"PASS client_list_windows: {len(windows)}")
            if not windows:
                print("FAIL no Factorio window; start a client first")
                return 1
            hwnd = windows[0]["hwnd"]
            for name, payload in (
                ("client_attach", {"hwnd": hwnd}),
                ("client_info", {}),
                ("client_focus", {}),
                ("client_screenshot", {"output": "state/shots/client-mcp-test.png", "scale": 0.5}),
            ):
                is_error, text = tool(name, payload)
                if is_error:
                    print(f"FAIL {name}: {text[:400]}")
                    return 1
                print(f"PASS {name}: {text[:200]}")
            if args.background:
                window = json.loads(tool("client_list_windows", {})[1])[0]
                for name, payload in (
                    ("client_input_attach", {"pid": window["pid"]}),
                    ("client_input_status", {}),
                    ("client_input_key", {"key": "shift", "action": "tap"}),
                    ("client_input_move", {"x": 1720, "y": 720}),
                    ("client_input_mouse_off", {}),
                    ("client_input_detach", {}),
                ):
                    is_error, text = tool(name, payload)
                    if is_error:
                        print(f"FAIL {name}: {text[:400]}")
                        return 1
                    print(f"PASS {name}: {text[:160]}")
            if args.actions:
                window = json.loads(tool("client_list_windows", {})[1])[0]
                for name, payload in (
                    ("client_action_attach", {"pid": window["pid"], "name": args.player_name}),
                    ("client_action_state", {}),
                    ("client_action_status", {}),
                    ("client_action_stop", {}),
                    ("client_action_detach", {}),
                ):
                    is_error, text = tool(name, payload)
                    if is_error:
                        print(f"FAIL {name}: {text[:400]}")
                        return 1
                    print(f"PASS {name}: {text[:160]}")
            if args.memory:
                window = json.loads(tool("client_list_windows", {})[1])[0]
                for name, payload in (
                    ("client_memory_attach", {"pid": window["pid"], "name": args.player_name}),
                    ("client_memory_status", {}),
                    ("client_memory_observe", {"radius": 16, "name": args.player_name}),
                    ("client_memory_inventory", {"name": args.player_name}),
                    ("client_memory_detach", {}),
                ):
                    is_error, text = tool(name, payload)
                    if is_error:
                        print(f"FAIL {name}: {text[:400]}")
                        return 1
                    print(f"PASS {name}: {text[:200]}")
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
