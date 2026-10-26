#!/usr/bin/env python3
"""Configure a freshly extracted FactorioAgent distribution.

This script only writes local state (state/webui.json) and creates runtime
directories. It does not download Factorio, start a server or modify a save.

Examples
--------
Interactive:
    python deploy/configure.py

Non-interactive (Windows example):
    python deploy/configure.py --server-exe "C:/Factorio/bin/x64/factorio.exe" --client-exe "C:/Factorio/bin/x64/factorio.exe" --rcon-password "replace-with-a-strong-password"

Validate an existing configuration:
    python deploy/configure.py --check

Print the masked configuration:
    python deploy/configure.py --print
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bridge.settings import CONFIG_PATH, load_config, masked_config, save_config  # noqa: E402


def _default(value: str | None, fallback: str) -> str:
    return (value or fallback or "").strip()


def _abs(value: str) -> str:
    if not value:
        return ""
    return str(Path(value).expanduser().resolve())


def _ask_path(label: str, current: str, required: bool = True) -> str:
    if current:
        print(f"{label}: {current}")
        answer = input("  Press Enter to keep, or enter a new path: ").strip().strip('"')
        if not answer:
            return current
        return answer
    if not required:
        return input(f"{label} (optional): ").strip().strip('"')
    while True:
        answer = input(f"{label}: ").strip().strip('"')
        if answer:
            return answer
        print("  This field is required.")


def validate(cfg: dict) -> list[str]:
    bot = cfg.get("bot", {})
    problems: list[str] = []
    checks = [
        ("server_exe", "Factorio server executable"),
        ("client_exe", "Factorio bot-client executable"),
        ("server_save", "real-player scenario save"),
        ("server_mods", "server mod directory"),
        ("server_settings", "server-settings JSON"),
    ]
    for key, label in checks:
        value = str(bot.get(key) or "").strip()
        if not value:
            problems.append(f"{label} is not configured (bot.{key})")
            continue
        if not Path(value).exists():
            problems.append(f"{label} does not exist: {value}")
    cfg_path = str(bot.get("server_config") or "").strip()
    if cfg_path and not Path(cfg_path).exists():
        problems.append(f"server config.ini does not exist: {cfg_path}")
    if not (ROOT / "server" / "agentbot-server-settings.json").exists():
        problems.append("missing server/agentbot-server-settings.json")
    if not (ROOT / "server" / "scenario-mods" / "mod-list.json").exists():
        problems.append("missing server/scenario-mods/mod-list.json")
    if sys.version_info < (3, 10):
        problems.append(f"Python is too old: {sys.version.split()[0]} (need 3.10+)")
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Configure FactorioAgent (local state only)")
    ap.add_argument("--server-exe", help="Factorio executable used by the headless server")
    ap.add_argument("--client-exe", help="standalone Factorio executable used by the second/bot client")
    ap.add_argument("--client-port", type=int, default=None, help="local UDP port for the bot client (default 34198)")
    ap.add_argument("--client-mods", help="bot client mod dir (default server/scenario-mods)")
    ap.add_argument("--client-mod-source", help="copy enabled mods from this mod dir before launch (e.g. the Steam profile)")
    ap.add_argument("--save", help="real-player scenario save (default: server/agentbot.zip)")
    ap.add_argument("--mods", help="server mod dir (default: server/scenario-mods)")
    ap.add_argument("--settings", help="server-settings JSON (default: server/agentbot-server-settings.json)")
    ap.add_argument("--server-config", help="optional Factorio --config file for a separate write-data")
    ap.add_argument("--rcon-host", default="127.0.0.1")
    ap.add_argument("--rcon-port", type=int, default=27017)
    ap.add_argument("--rcon-password", help="RCON password; generated when omitted")
    ap.add_argument("--player-name", default="LLM-Bot")
    ap.add_argument("--webui-host", default="127.0.0.1")
    ap.add_argument("--webui-port", type=int, default=8090)
    ap.add_argument("--goal", help="long-running agent goal")
    ap.add_argument("--no-input", action="store_true", help="fail instead of prompting")
    ap.add_argument("--check", action="store_true", help="only validate the current configuration")
    ap.add_argument("--print", action="store_true", dest="print_config", help="print the masked configuration")
    a = ap.parse_args(argv)

    cfg = load_config()
    bot = cfg.setdefault("bot", {})
    llm = cfg.setdefault("llm", {})
    webui = cfg.setdefault("webui", {})

    if a.check or a.print_config:
        problems = validate(cfg)
        shown = masked_config(cfg)
        shown.setdefault("bot", {})["rcon_password"] = "***" if cfg.get("bot", {}).get("rcon_password") else ""
        print(json.dumps(shown, ensure_ascii=False, indent=2))
        if problems:
            print("\nConfiguration problems:", file=sys.stderr)
            for p in problems:
                print(" -", p, file=sys.stderr)
            return 1
        print("\nConfiguration OK.")
        return 0

    interactive = not a.no_input and sys.stdin.isatty()
    server_exe = _default(a.server_exe, bot.get("server_exe") or os.environ.get("FACTORIO_EXE", ""))
    client_exe = _default(a.client_exe, bot.get("client_exe") or os.environ.get("FACTORIO_CLIENT_EXE", "") or server_exe)
    if interactive:
        server_exe = _ask_path("Factorio server executable", server_exe)
        client_exe = _ask_path("Factorio bot-client executable (may be the same)", client_exe)
    if not server_exe:
        print("error: --server-exe is required (or set FACTORIO_EXE).", file=sys.stderr)
        return 2
    server_exe = _abs(server_exe)
    client_exe = _abs(client_exe)
    if not Path(server_exe).exists():
        print(f"warning: server executable not found: {server_exe}", file=sys.stderr)
    if client_exe and not Path(client_exe).exists():
        print(f"warning: bot-client executable not found: {client_exe}", file=sys.stderr)

    save = _abs(_default(a.save, bot.get("server_save") or str(ROOT / "server" / "agentbot.zip")))
    mods = _abs(_default(a.mods, bot.get("server_mods") or str(ROOT / "server" / "scenario-mods")))
    settings = _abs(_default(a.settings, bot.get("server_settings") or str(ROOT / "server" / "agentbot-server-settings.json")))
    server_config = _abs(_default(a.server_config, bot.get("server_config") or ""))
    password = a.rcon_password or bot.get("rcon_password") or ""
    generated = False
    if not password:
        password = secrets.token_urlsafe(12)
        generated = True

    bot.update({
        "server_exe": server_exe,
        "client_exe": client_exe or server_exe,
        "client_port": int(a.client_port or bot.get("client_port") or 34198),
        "client_data_dir": _abs(bot.get("client_data_dir") or str(ROOT / "bot-data")),
        "client_mod_dir": _abs(a.client_mods or bot.get("client_mod_dir") or str(ROOT / "server" / "scenario-mods")),
        "client_mod_source": _abs(a.client_mod_source or bot.get("client_mod_source") or ""),
        "server_save": save,
        "server_mods": mods,
        "server_settings": settings,
        "server_config": server_config,
        "rcon_port": int(a.rcon_port),
        "rcon_password": password,
        "host": a.rcon_host,
        "player_name": a.player_name,
    })
    if a.goal:
        bot["goal"] = a.goal
    webui.update({"host": a.webui_host, "port": int(a.webui_port)})
    if not llm.get("provider"):
        llm["provider"] = "auto"

    for d in (ROOT / "state", ROOT / "state" / "blueprints", ROOT / "bot-data",
              ROOT / "server-data" / "saves", ROOT / "server-data" / "temp"):
        d.mkdir(parents=True, exist_ok=True)

    save_config(cfg)
    problems = validate(cfg)
    print(f"written: {CONFIG_PATH}")
    print(f"RCON: {a.rcon_host}:{a.rcon_port}")
    print(f"Web console: http://{a.webui_host}:{a.webui_port}")
    print(f"real-player save: {save}")
    print(f"bot client port: {bot['client_port']} (server port is 34197)")
    if generated:
        print(f"generated RCON password: {password}")
        print("  It is also stored in state/webui.json; do not commit that file.")
    if problems:
        print("\nRemaining items:", file=sys.stderr)
        for p in problems:
            print(" -", p, file=sys.stderr)
        return 1
    print("\nNext steps:")
    print("  python -m bridge.webui            # open the console")
    print("  python -m bridge.cli observe       # check RCON/player state")
    print("  python tests/mcp_smoke.py --live   # read-only self-test after server+client start")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
