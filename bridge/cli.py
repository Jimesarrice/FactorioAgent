"""Command line front-end for the Factorio agent connector."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from .agent import AgentBridge
from .server import FactorioServer

ROOT = Path(__file__).resolve().parents[1]


def _server_from_args(a) -> FactorioServer:
    return FactorioServer(
        factorio_exe=a.exe or os.environ.get("FACTORIO_EXE") or str(ROOT / "standalone" / "bin" / "x64" / "factorio.exe"),
        save=a.save or os.environ.get("FACTORIO_SAVE") or str(ROOT / "server" / "lab.zip"),
        mod_dir=a.mods or os.environ.get("FACTORIO_MODS") or str(ROOT / "mods"),
        server_settings=a.settings or os.environ.get("FACTORIO_SETTINGS") or str(ROOT / "server" / "lab-server-settings.json"),
        port=a.port,
        rcon_port=a.rcon_port,
        rcon_password=a.rcon_password,
        rcon_bind=a.rcon_bind,
        lua_udp_port=a.lua_udp_port,
        config=a.config,
    )


def _bridge(a) -> AgentBridge:
    return AgentBridge(a.host, a.rcon_port, a.rcon_password)


def cmd_start(a):
    srv = _server_from_args(a)
    print("starting:", " ".join(srv.args()))
    srv.start()
    srv.wait_ready()
    print(f"server ready: RCON 127.0.0.1:{srv.rcon_port}, game UDP :{a.port}")
    print("tail:", srv.log_path)


def cmd_stop(a):
    br = _bridge(a)
    print("save:", br.save())
    try:
        br.rc.execute("/quit", timeout=3)
    except Exception:
        pass
    br.close()


def cmd_observe(a):
    br = _bridge(a)
    print(br.observe_text(a.radius))
    br.close()


def cmd_state(a):
    br = _bridge(a)
    print(json.dumps(br.state(a.radius), indent=2, ensure_ascii=False))
    br.close()


def cmd_scan(a):
    br = _bridge(a)
    print(json.dumps(br.scan(a.radius), indent=2, ensure_ascii=False))
    br.close()


def cmd_tool(a):
    br = _bridge(a)
    args = json.loads(a.args) if a.args else {}
    print(br.execute_tool(a.name, args))
    br.close()


def cmd_submit(a):
    br = _bridge(a)
    action = json.loads(a.action)
    print(json.dumps(br.submit(action), ensure_ascii=False))
    br.close()


def cmd_wait(a):
    br = _bridge(a)
    print(json.dumps(br.wait_job(a.id, timeout=a.timeout), ensure_ascii=False))
    br.close()


def cmd_save(a):
    br = _bridge(a)
    print(json.dumps(br.save(), ensure_ascii=False))
    br.close()


def cmd_pause(a):
    br = _bridge(a)
    print(json.dumps(br.pause(True), ensure_ascii=False))
    br.close()


def cmd_resume(a):
    br = _bridge(a)
    print(json.dumps(br.pause(False), ensure_ascii=False))
    br.close()


def cmd_speed(a):
    br = _bridge(a)
    print(json.dumps(br.speed(a.value), ensure_ascii=False))
    br.close()


def cmd_raw(a):
    br = _bridge(a)
    print(br.rc.execute(a.command))
    br.close()


def cmd_init_lab(a):
    br = _bridge(a)
    # These are the vanilla free/starting technologies.  A save created with
    # --create never had a player join, so the engine did not grant them.
    cmd = ('/c local f=game.forces.player; '
           'for _,n in pairs({"electronics","steam-power","automation-science-pack","logistics"}) do '
           'if f.technologies[n] then f.technologies[n].researched=true end end; '
           'rcon.print("lab starting techs initialized")')
    print(br.rc.execute(cmd).strip())
    br.save()
    br.close()


def cmd_bot(a):
    from .bot_loop import DEFAULT_GOAL, run_bot
    run_bot(a.goal or DEFAULT_GOAL,
            start_server=a.start_server, start_client=a.start_client,
            client_exe=a.client_exe, player_name=a.player_name,
            interval=a.interval, max_cycles=a.max_cycles, turns=a.turns,
            model=a.model, host=a.host, port=a.rcon_port,
            password=a.rcon_password, turn_based=a.turn_based,
            server_save=a.save, server_mods=a.mods, server_settings=a.settings,
            server_exe=a.exe, server_config=a.config)


def cmd_llm(a):
    from .llm_agent import LLMAgent

    srv = None
    if a.start_server:
        srv = _server_from_args(a)
        srv.start()
        srv.wait_ready()
    try:
        br = _bridge(a)
        agent = LLMAgent(br, model=a.model, log_path=ROOT / "state" / "llm-run.jsonl")
        print(agent.run(a.task, max_turns=a.max_turns, turn_based=a.turn_based))
        br.save()
        br.close()
    finally:
        if srv:
            srv.stop(save=True)


def add_conn(p):
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--rcon-port", type=int, default=27016)
    p.add_argument("--rcon-password", default="test")
    p.add_argument("--radius", type=float, default=18)


def add_server(p):
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--exe")
    p.add_argument("--save")
    p.add_argument("--mods")
    p.add_argument("--settings")
    p.add_argument("--config")
    p.add_argument("--port", type=int, default=34197)
    p.add_argument("--rcon-port", type=int, default=27016)
    p.add_argument("--rcon-password", default="test")
    p.add_argument("--rcon-bind", help="e.g. 127.0.0.1:27016 (takes precedence over --rcon-port)")
    p.add_argument("--lua-udp-port", type=int, default=None, help="optional --enable-lua-udp port (unused by the current mod)")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Embodied Factorio LLM agent connector")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("start", help="start the headless server")
    add_server(p); p.set_defaults(fn=cmd_start)

    p = sub.add_parser("stop", help="save and quit the server")
    add_conn(p); p.set_defaults(fn=cmd_stop)

    p = sub.add_parser("observe", help="compact observation text")
    add_conn(p); p.set_defaults(fn=cmd_observe)

    p = sub.add_parser("state", help="full JSON state")
    add_conn(p); p.set_defaults(fn=cmd_state)

    p = sub.add_parser("scan", help="resources and entities in a radius")
    add_conn(p); p.set_defaults(fn=cmd_scan)

    p = sub.add_parser("tool", help="run one LLM tool by name")
    add_conn(p); p.add_argument("name"); p.add_argument("args", nargs="?", default="{}")
    p.set_defaults(fn=cmd_tool)

    p = sub.add_parser("submit", help="submit a raw action JSON")
    add_conn(p); p.add_argument("action"); p.set_defaults(fn=cmd_submit)

    p = sub.add_parser("wait", help="wait for a job id")
    add_conn(p); p.add_argument("id", type=int); p.add_argument("--timeout", type=float, default=180)
    p.set_defaults(fn=cmd_wait)

    p = sub.add_parser("save", help="save the map")
    add_conn(p); p.set_defaults(fn=cmd_save)

    p = sub.add_parser("pause", help="pause the simulation")
    add_conn(p); p.set_defaults(fn=cmd_pause)

    p = sub.add_parser("resume", help="resume the simulation")
    add_conn(p); p.set_defaults(fn=cmd_resume)

    p = sub.add_parser("speed", help="set game speed (1 = normal)")
    add_conn(p); p.add_argument("value", type=float); p.set_defaults(fn=cmd_speed)

    p = sub.add_parser("raw", help="run one RCON console command")
    add_conn(p); p.add_argument("command"); p.set_defaults(fn=cmd_raw)

    p = sub.add_parser("init-lab", help="grant the vanilla starting techs to a headless lab save")
    add_conn(p); p.set_defaults(fn=cmd_init_lab)

    p = sub.add_parser("bot", help="long-running real-player LLM bot on the agentbot scenario")
    add_server(p)
    p.set_defaults(rcon_port=27017)
    p.add_argument("--start-server", action="store_true")
    p.add_argument("--start-client", action="store_true")
    p.add_argument("--client-exe", help="standalone Factorio client executable for the bot body")
    p.add_argument("--player-name", default="LLM-Bot")
    p.add_argument("--goal", default=None)
    p.add_argument("--interval", type=float, default=8.0)
    p.add_argument("--max-cycles", type=int, default=0)
    p.add_argument("--turns", type=int, default=8)
    p.add_argument("--model")
    p.add_argument("--turn-based", action="store_true")
    p.set_defaults(fn=cmd_bot)

    p = sub.add_parser("llm", help="run an OpenAI-compatible tool-calling agent")
    add_server(p)
    p.add_argument("--task", required=True)
    p.add_argument("--max-turns", type=int, default=25)
    p.add_argument("--model")
    p.add_argument("--turn-based", action="store_true", help="pause the game while the LLM thinks")
    p.add_argument("--start-server", action="store_true")
    p.set_defaults(fn=cmd_llm)

    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
