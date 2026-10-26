"""Long-running LLM loop for a real-player bot on the agentbot scenario."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from .agent import AgentBridge, format_observation
from .bot_client import BotClient
from .llm_agent import LLMAgent
from .server import FactorioServer

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_GOAL = """Complete Factorio: Space Age with the real player LLM-Bot.
Progress through automation, power, trains/logistics, research, rocket launches,
space platforms, and the planets Vulcanus, Fulgora, Gleba, Aquilo, and finally the
Shattered Planet. Work autonomously, but obey instructions from the console.
Never use cheats or direct item creation; use normal player actions."""


def run_bot(goal: str = DEFAULT_GOAL, *, start_server: bool = False,
            start_client: bool = False, client_exe: str | None = None,
            client_port: int = 34198, client_data_dir: str | None = None,
            client_mod_dir: str | None = None, client_mod_source: str | None = None,
            player_name: str = "LLM-Bot", interval: float = 8.0,
            max_cycles: int = 0, turns: int = 8, model: str | None = None,
            host: str = "127.0.0.1", port: int = 27017,
            password: str = "test", turn_based: bool = False,
            server_save: str | None = None, server_mods: str | None = None,
            server_settings: str | None = None, server_exe: str | None = None,
            server_config: str | None = None, llm_settings: dict | None = None,
            event_log: str | None = None, stop_file: str | None = None,
            log_path: str | None = None) -> None:
    srv = None
    client = None
    if stop_file:
        try:
            Path(stop_file).unlink()
        except FileNotFoundError:
            pass
    if start_server:
        srv = FactorioServer(
            factorio_exe=server_exe or str(ROOT / "standalone" / "bin" / "x64" / "factorio.exe"),
            save=server_save or str(ROOT / "server" / "agentbot.zip"),
            mod_dir=server_mods or str(ROOT / "server" / "scenario-mods"),
            server_settings=server_settings or str(ROOT / "server" / "agentbot-server-settings.json"),
            rcon_port=port, rcon_password=password, lua_udp_port=None,
            config=server_config or (str(ROOT / "server-data" / "config.ini")
                                     if (ROOT / "server-data" / "config.ini").exists() else None),
            log_path=str(ROOT / "server" / "agentbot-stdout.log"),
        )
        srv.start(); srv.wait_ready()
    try:
        bridge = AgentBridge(host, port, password)
        bridge.set_bot_name(player_name)
        if start_client:
            if not client_exe:
                raise SystemExit("--start-client needs --client-exe (standalone Factorio client)")
            if client_mod_source:
                from .bot_client import sync_mods
                sync_mods(client_mod_source, client_mod_dir or str(ROOT / "server" / "scenario-mods"))
            client = BotClient(client_exe, host, 34197, player_name,
                               data_dir=client_data_dir, mod_dir=client_mod_dir,
                               client_port=client_port,
                               log_path=str(ROOT / "server" / "bot-client.log"))
            client.start()
        # If the client is already running, wait for the scenario to see it.
        try:
            if client:
                client.wait_connected(bridge, timeout=180)
            else:
                # wait for a manually started bot client
                deadline = time.time() + 120
                while time.time() < deadline:
                    p = bridge.state().get("player") or {}
                    if p.get("connected") and p.get("name") == player_name:
                        break
                    time.sleep(2)
        except Exception as e:
            print(f"[bot] waiting for player failed: {e}")

        llm = LLMAgent(bridge, model=model, llm_settings=llm_settings,
                       log_path=Path(log_path) if log_path else ROOT / "state" / "bot-run.jsonl",
                       event_log=event_log or str(ROOT / "state" / "bot-events.jsonl"))
        memory = ""
        last_inbox_seq = 0
        cycle = 0
        while max_cycles <= 0 or cycle < max_cycles:
            if stop_file and Path(stop_file).exists():
                print("[bot] stop flag received", flush=True)
                break
            cycle += 1
            try:
                state = bridge.state()
                inbox = bridge.inbox(last_inbox_seq).get("events", [])
                last_inbox_seq = max([last_inbox_seq] + [e.get("seq", 0) for e in inbox])
                instructions = "\n".join(
                    f"- {e.get('kind')}: {e.get('text')}" for e in inbox) or "(none)"
                task = (f"GOAL:\n{goal}\n\nMEMORY FROM PREVIOUS CYCLES:\n{memory or '(none)'}\n\n"
                        f"CONSOLE INSTRUCTIONS (highest priority):\n{instructions}\n\n"
                        f"CURRENT OBSERVATION:\n{format_observation(state)}\n\n"
                        "Take the next concrete actions with tools. If a console instruction is present, "
                        "handle it first and report back with say(). Be concise.")
                reply = llm.run(task, max_turns=turns, turn_based=turn_based, verbose=True)
                actions = getattr(llm, "last_summary", "")
                if reply or actions:
                    block = (reply or "") + ("\nACTIONS: " + actions if actions else "")
                    memory = (memory + "\n" + block).strip()[-6000:]
                print(f"[bot] cycle {cycle} done: {reply[:300]}")
            except Exception as e:
                print(f"[bot] cycle {cycle} error: {type(e).__name__}: {e}")
            time.sleep(max(1.0, interval))
    finally:
        try:
            llm.close()
        except Exception:
            pass
        if client:
            client.stop()
        if srv:
            srv.stop(save=True)


def main() -> None:
    import argparse
    from .settings import EVENT_LOG, STOP_FILE, bot_kwargs, load_config

    ap = argparse.ArgumentParser(description="Long-running Factorio real-player LLM bot")
    ap.add_argument("--config", help="JSON config from the web console (settings.py schema)")
    ap.add_argument("--goal")
    ap.add_argument("--start-server", action="store_true")
    ap.add_argument("--start-client", action="store_true")
    ap.add_argument("--client-exe")
    ap.add_argument("--client-port", type=int, default=34198)
    ap.add_argument("--client-data-dir")
    ap.add_argument("--client-mod-dir")
    ap.add_argument("--client-mod-source")
    ap.add_argument("--player-name", default="LLM-Bot")
    ap.add_argument("--interval", type=float, default=8.0)
    ap.add_argument("--max-cycles", type=int, default=0)
    ap.add_argument("--turns", type=int, default=8)
    ap.add_argument("--model")
    ap.add_argument("--turn-based", action="store_true")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--rcon-port", type=int, default=27017)
    ap.add_argument("--rcon-password", default="test")
    ap.add_argument("--server-save")
    ap.add_argument("--server-mods")
    ap.add_argument("--server-settings")
    ap.add_argument("--server-exe")
    ap.add_argument("--server-config")
    ap.add_argument("--event-log")
    ap.add_argument("--stop-file")
    a = ap.parse_args()

    if a.config:
        cfg = load_config()
        kwargs = bot_kwargs(cfg)
        if a.goal:
            kwargs["goal"] = a.goal
        if a.start_server:
            kwargs["start_server"] = True
        if a.start_client:
            kwargs["start_client"] = True
        if a.client_exe:
            kwargs["client_exe"] = a.client_exe
        if a.client_port:
            kwargs["client_port"] = a.client_port
        if a.client_data_dir:
            kwargs["client_data_dir"] = a.client_data_dir
        if a.client_mod_dir:
            kwargs["client_mod_dir"] = a.client_mod_dir
        if a.client_mod_source:
            kwargs["client_mod_source"] = a.client_mod_source
        if a.event_log:
            kwargs["event_log"] = a.event_log
        if a.stop_file:
            kwargs["stop_file"] = a.stop_file
        run_bot(**kwargs)
        return

    run_bot(a.goal or DEFAULT_GOAL, start_server=a.start_server, start_client=a.start_client,
            client_exe=a.client_exe, client_port=a.client_port,
            client_data_dir=a.client_data_dir, client_mod_dir=a.client_mod_dir,
            client_mod_source=a.client_mod_source,
            player_name=a.player_name, interval=a.interval,
            max_cycles=a.max_cycles, turns=a.turns, model=a.model,
            turn_based=a.turn_based, host=a.host, port=a.rcon_port,
            password=a.rcon_password, server_save=a.server_save, server_mods=a.server_mods,
            server_settings=a.server_settings, server_exe=a.server_exe,
            server_config=a.server_config, event_log=a.event_log or str(EVENT_LOG),
            stop_file=a.stop_file or str(STOP_FILE))


if __name__ == "__main__":
    main()
