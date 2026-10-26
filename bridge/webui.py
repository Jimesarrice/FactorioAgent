"""Local web console for the Factorio real-player LLM bot.

The console is intentionally dependency-free (stdlib http.server).  It binds to
127.0.0.1 by default, shows provider-supplied reasoning plus tool/decision logs,
and can start/stop the bot loop, send console instructions and edit config.

WARNING: the config file stores local API keys in plain text; keep the console
on localhost and do not expose it to the network.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .agent import AgentBridge
from .llm_agent import LLMAgent
from .settings import (CONFIG_PATH, EVENT_LOG, ROOT, STOP_FILE, bot_kwargs,
                       load_config, masked_config, save_config)

WEB_DIR = ROOT / "webui"


class BotManager:
    def __init__(self):
        self.lock = threading.RLock()
        self.proc: subprocess.Popen | None = None
        self.log_path = ROOT / "state" / "webui-bot.out"
        self._log = None
        self.bridge: AgentBridge | None = None
        self.phase = "idle"       # idle | running | stopped | exited
        self.exit_code: int | None = None

    def _refresh(self) -> None:
        """Close a finished child and remember whether it exited by itself."""
        if self.proc is not None and self.proc.poll() is not None:
            self.exit_code = self.proc.returncode
            if self.phase == "running":
                self.phase = "exited"
            self.proc = None
            if self._log:
                try:
                    self._log.close()
                finally:
                    self._log = None

    def status(self) -> dict:
        with self.lock:
            self._refresh()
            running = bool(self.proc and self.proc.poll() is None)
            return {
                "running": running,
                "phase": self.phase,
                "pid": self.proc.pid if running and self.proc else None,
                "exit_code": self.exit_code,
                "log_tail": self.tail(40),
                "events": str(EVENT_LOG),
            }

    def tail(self, lines: int = 40) -> str:
        p = self.log_path
        if not p.exists():
            return ""
        try:
            return "\n".join(p.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])
        except Exception:
            return ""

    def start(self) -> dict:
        with self.lock:
            if self.proc and self.proc.poll() is None:
                return {"ok": False, "error": "bot is already running", **self.status()}
            try:
                STOP_FILE.unlink()
            except FileNotFoundError:
                pass
            EVENT_LOG.parent.mkdir(parents=True, exist_ok=True)
            EVENT_LOG.write_text("", encoding="utf-8")
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log = open(self.log_path, "w", encoding="utf-8", errors="replace")
            cmd = [sys.executable, "-m", "bridge.bot_loop", "--config", str(CONFIG_PATH)]
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
            env = dict(os.environ)
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUTF8"] = "1"
            self.proc = subprocess.Popen(cmd, cwd=str(ROOT), stdin=subprocess.DEVNULL,
                                         stdout=self._log, stderr=subprocess.STDOUT,
                                         env=env, creationflags=flags)
            self.phase = "running"
            self.exit_code = None
            return {"ok": True, **self.status()}

    def stop(self) -> dict:
        with self.lock:
            if not self.proc or self.proc.poll() is not None:
                return {"ok": True, **self.status()}
            # Persist game progress before asking the loop to stop.  A slow local
            # model may exceed the stop grace period and be force-killed.
            try:
                self.get_bridge(load_config()).save()
            except Exception:
                pass
            try:
                STOP_FILE.write_text("stop", encoding="utf-8")
            except Exception:
                pass
            deadline = time.time() + 60
            while time.time() < deadline:
                if self.proc.poll() is not None:
                    break
                time.sleep(0.5)
            if self.proc and self.proc.poll() is None:
                try:
                    if sys.platform == "win32":
                        subprocess.run(["taskkill", "/PID", str(self.proc.pid), "/T", "/F"],
                                       capture_output=True, timeout=20)
                    else:
                        self.proc.terminate()
                except Exception:
                    pass
            try:
                self.proc.wait(timeout=10)
            except Exception:
                pass
            try:
                STOP_FILE.unlink()
            except FileNotFoundError:
                pass
            self.exit_code = self.proc.returncode
            self.phase = "stopped"
            if self._log:
                self._log.close()
                self._log = None
            self.proc = None
            return {"ok": True, **self.status()}

    def get_bridge(self, cfg: dict) -> AgentBridge:
        with self.lock:
            b = cfg["bot"]
            if self.bridge is None:
                self.bridge = AgentBridge(b.get("host", "127.0.0.1"),
                                          int(b.get("rcon_port", 27017)),
                                          b.get("rcon_password", "test"))
            return self.bridge

    def reset_bridge(self) -> None:
        with self.lock:
            if self.bridge:
                try:
                    self.bridge.close()
                except Exception:
                    pass
                self.bridge = None

    def game_state(self, cfg: dict) -> dict:
        for _ in range(2):
            try:
                return {"ok": True, "state": self.get_bridge(cfg).state()}
            except Exception as e:
                self.reset_bridge()
                last = str(e)
                time.sleep(0.2)
        return {"ok": False, "error": last}

    def control(self, action: str, payload: dict, cfg: dict) -> dict:
        if action == "start":
            return self.start()
        if action == "stop":
            return self.stop()
        if action == "pause":
            return self.get_bridge(cfg).pause(True)
        if action == "resume":
            return self.get_bridge(cfg).pause(False)
        if action == "save":
            return self.get_bridge(cfg).save()
        if action == "instruct":
            return self.get_bridge(cfg).instruct(str(payload.get("text", "")))
        if action == "set_eval":
            return self.get_bridge(cfg).set_eval(bool(payload.get("enabled")))
        return {"ok": False, "error": f"unknown action {action}"}


MANAGER = BotManager()


def read_events(limit: int = 400) -> list[dict]:
    if not EVENT_LOG.exists():
        return []
    try:
        data = EVENT_LOG.read_bytes()
        if len(data) > 2 * 1024 * 1024:
            data = data[-2 * 1024 * 1024:]
        lines = data.decode("utf-8", "replace").splitlines()
    except Exception:
        return []
    out = []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
            if isinstance(rec, dict):
                out.append(rec)
        except json.JSONDecodeError:
            continue
    return out


class Handler(BaseHTTPRequestHandler):
    server_version = "FactorioAgentWeb/1.0"

    def _json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            data = json.loads(raw.decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _static(self, name: str, content_type: str):
        path = WEB_DIR / name
        if not path.exists():
            self.send_error(404)
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)
        cfg = load_config()
        if path in ("/", "/index.html"):
            return self._static("index.html", "text/html; charset=utf-8")
        if path == "/app.js":
            return self._static("app.js", "application/javascript; charset=utf-8")
        if path == "/style.css":
            return self._static("style.css", "text/css; charset=utf-8")
        if path == "/api/config":
            return self._json(masked_config(cfg))
        if path == "/api/status":
            return self._json({"ok": True, "bot": MANAGER.status()})
        if path == "/api/state":
            st = MANAGER.game_state(cfg)
            st["bot"] = MANAGER.status()
            st["llm"] = {"provider": cfg["llm"].get("provider"),
                         "local_model": cfg["llm"].get("local_model"),
                         "cloud_model": cfg["llm"].get("cloud_model")}
            return self._json(st)
        if path == "/api/logs":
            try:
                limit = int(qs.get("limit", ["400"])[0])
            except ValueError:
                limit = 400
            return self._json({"ok": True, "events": read_events(limit)})
        if path == "/api/models":
            provider = qs.get("provider", ["local"])[0]
            llm = cfg["llm"]
            if provider == "cloud":
                base, key = llm.get("cloud_base_url"), llm.get("cloud_api_key", "")
            else:
                base, key = llm.get("local_base_url"), llm.get("local_api_key", "")
            return self._json(LLMAgent.list_models(base, key))
        self.send_error(404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        payload = self._body()
        cfg = load_config()
        if parsed.path == "/api/config":
            incoming = payload.get("config", payload)
            if not isinstance(incoming, dict):
                return self._json({"ok": False, "error": "invalid config"}, 400)
            merged = cfg
            for section in ("llm", "bot", "webui"):
                if isinstance(incoming.get(section), dict):
                    merged.setdefault(section, {}).update(incoming[section])
            save_config(merged)
            MANAGER.reset_bridge()
            return self._json({"ok": True, "config": masked_config(load_config())})
        if parsed.path == "/api/control":
            action = payload.get("action", "")
            try:
                return self._json(MANAGER.control(action, payload, cfg))
            except Exception as e:
                MANAGER.reset_bridge()
                return self._json({"ok": False, "error": f"{type(e).__name__}: {e}"})
        if parsed.path == "/api/models":
            provider = payload.get("provider", "local")
            base = payload.get("base_url", "")
            key = payload.get("api_key", "")
            if key in ("", "***", None):
                llm = cfg["llm"]
                key = llm.get("cloud_api_key") if provider == "cloud" else llm.get("local_api_key")
            if not base:
                llm = cfg["llm"]
                base = llm.get("cloud_base_url") if provider == "cloud" else llm.get("local_base_url")
            return self._json(LLMAgent.list_models(base, key or ""))
        self.send_error(404)

    def log_message(self, fmt, *args):
        print(f"[webui] {self.address_string()} {fmt % args}", flush=True)


def main():
    import argparse
    from .settings import load_config
    cfg = load_config()
    ap = argparse.ArgumentParser(description="Factorio real-player LLM web console")
    ap.add_argument("--host", default=cfg["webui"].get("host", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(cfg["webui"].get("port", 8090)))
    a = ap.parse_args()
    server = ThreadingHTTPServer((a.host, a.port), Handler)
    print(f"[webui] http://{a.host}:{a.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        MANAGER.stop()
        server.server_close()


if __name__ == "__main__":
    main()
