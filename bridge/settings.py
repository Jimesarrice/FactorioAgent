"""Local settings for the web console and bot loop."""
from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "state" / "webui.json"
EVENT_LOG = ROOT / "state" / "bot-events.jsonl"
STOP_FILE = ROOT / "state" / "bot-stop.flag"

DEFAULTS = {
    "llm": {
        "provider": "auto",
        "local_base_url": "http://127.0.0.1:11434/v1",
        "local_model": "Q3.5-9B:latest",
        "local_api_key": "",
        "cloud_base_url": "https://api.openai.com/v1",
        "cloud_model": "gpt-4o-mini",
        "cloud_api_key": "",
        "fallback_cloud": True,
        "temperature": 0.2,
    },
    "bot": {
        "goal": ("From the crashed ship, complete Factorio: Space Age. Automate production, "
                 "research, launch rockets, build space platforms, visit Vulcanus, Fulgora, "
                 "Gleba and Aquilo, and finally reach the Shattered Planet."),
        "player_name": "LLM-Bot",
        "interval": 8.0,
        "turns": 8,
        "turn_based": True,
        "start_server": True,
        "start_client": True,
        "server_exe": os.environ.get("FACTORIO_EXE", ""),
        "client_exe": os.environ.get("FACTORIO_CLIENT_EXE", os.environ.get("FACTORIO_EXE", "")),
        "client_port": 34198,
        "client_data_dir": str(ROOT / "bot-data"),
        "client_mod_dir": str(ROOT / "server" / "scenario-mods"),
        "client_mod_source": "",
        "server_save": str(ROOT / "server" / "agentbot.zip"),
        "server_mods": str(ROOT / "server" / "scenario-mods"),
        "server_settings": str(ROOT / "server" / "agentbot-server-settings.json"),
        "server_config": os.environ.get("FACTORIO_CONFIG", ""),
        "rcon_port": 27017,
        "rcon_password": "test",
        "host": "127.0.0.1",
    },
    "webui": {"host": "127.0.0.1", "port": 8090},
}


def _merge(base: dict, incoming: dict) -> dict:
    out = deepcopy(base)
    for k, v in (incoming or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    else:
        data = {}
    cfg = _merge(DEFAULTS, data)
    # environment fallback (cloud keeps the old behavior)
    llm = cfg["llm"]
    if not llm.get("cloud_api_key"):
        llm["cloud_api_key"] = os.environ.get("OPENAI_API_KEY", "")
    if not llm.get("cloud_base_url"):
        llm["cloud_base_url"] = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    if not llm.get("cloud_model"):
        llm["cloud_model"] = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    if not llm.get("local_base_url"):
        llm["local_base_url"] = os.environ.get("LOCAL_LLM_BASE_URL", "")
    if not llm.get("local_model"):
        llm["local_model"] = os.environ.get("LOCAL_LLM_MODEL", "")
    if not llm.get("provider"):
        llm["provider"] = os.environ.get("LLM_PROVIDER", "auto")
    return cfg


def save_config(cfg: dict) -> dict:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Never write the mask back over a real secret.
    old = {}
    if CONFIG_PATH.exists():
        try:
            old = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            old = {}
    llm = cfg.setdefault("llm", {})
    old_llm = old.get("llm", {})
    for key in ("local_api_key", "cloud_api_key"):
        if llm.get(key) in ("", "***", None):
            llm[key] = old_llm.get(key, "")
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return cfg


def masked_config(cfg: dict) -> dict:
    out = deepcopy(cfg)
    llm = out.setdefault("llm", {})
    for key in ("local_api_key", "cloud_api_key"):
        if llm.get(key):
            llm[key] = "***"
    return out


def bot_kwargs(cfg: dict) -> dict:
    b = cfg["bot"]
    return {
        "goal": b["goal"],
        "start_server": bool(b.get("start_server")),
        "start_client": bool(b.get("start_client")),
        "client_exe": b.get("client_exe"),
        "client_port": int(b.get("client_port", 34198)),
        "client_data_dir": b.get("client_data_dir"),
        "client_mod_dir": b.get("client_mod_dir"),
        "client_mod_source": b.get("client_mod_source") or None,
        "player_name": b.get("player_name", "LLM-Bot"),
        "interval": float(b.get("interval", 8)),
        "max_cycles": 0,
        "turns": int(b.get("turns", 8)),
        "turn_based": bool(b.get("turn_based", True)),
        "host": b.get("host", "127.0.0.1"),
        "port": int(b.get("rcon_port", 27017)),
        "password": b.get("rcon_password", "test"),
        "server_save": b.get("server_save"),
        "server_mods": b.get("server_mods"),
        "server_settings": b.get("server_settings"),
        "server_exe": b.get("server_exe"),
        "server_config": b.get("server_config"),
        "llm_settings": cfg.get("llm", {}),
        "event_log": str(EVENT_LOG),
        "stop_file": str(STOP_FILE),
    }
