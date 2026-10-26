"""Process lifecycle for a headless Factorio server used by an LLM agent."""
from __future__ import annotations

import os
import shutil
import socket
import subprocess
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FACTORIO = os.environ.get(
    "FACTORIO_EXE", str(_ROOT / "standalone" / "bin" / "x64" / "factorio.exe"))
DEFAULT_MOD_DIR = str(_ROOT / "mods")
DEFAULT_SAVE = str(_ROOT / "server" / "lab.zip")


def _port_open(host: str, port: int, timeout: float = 0.3) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


class FactorioServer:
    """Owns one headless Factorio process.

    The server is deliberately started with ``auto_pause=false`` (see the
    server-settings file): without a connected GUI client the simulation must
    still tick so the mod-created character and the job queue can run.
    """

    def __init__(self, factorio_exe: str = DEFAULT_FACTORIO,
                 save: str = DEFAULT_SAVE,
                 mod_dir: str = DEFAULT_MOD_DIR,
                 server_settings: str | None = None,
                 port: int = 34197,
                 rcon_port: int = 27016,
                 rcon_password: str = "test",
                 rcon_bind: str | None = None,
                 lua_udp_port: int | None = None,
                 config: str | None = None,
                 log_path: str | None = None):
        # Factorio is launched with cwd=<exe dir>; resolve every path against
        # the caller's cwd so relative --save/--mods examples still work.
        self.factorio_exe = str(Path(factorio_exe).expanduser().resolve())
        self.save = str(Path(save).expanduser().resolve())
        self.mod_dir = str(Path(mod_dir).expanduser().resolve())
        self.server_settings = (str(Path(server_settings).expanduser().resolve())
                                if server_settings else None)
        self.port = port
        if rcon_bind:
            _host, _sep, _port = str(rcon_bind).rpartition(":")
            if _sep and _port.isdigit():
                rcon_port = int(_port)
        self.rcon_port = rcon_port
        self.rcon_password = rcon_password
        self.rcon_bind = rcon_bind
        self.lua_udp_port = lua_udp_port
        self.config = str(Path(config).expanduser().resolve()) if config else None
        self.log_path = log_path or str(Path(self.save).with_name("server-stdout.log"))
        self.proc: subprocess.Popen | None = None
        self._log_handle = None

    # -- basic lifecycle -----------------------------------------------------

    def args(self) -> list[str]:
        args = [
            self.factorio_exe,
            "--start-server", self.save,
            "--mod-directory", self.mod_dir,
            "--port", str(self.port),
            *(["--rcon-bind", self.rcon_bind] if self.rcon_bind else ["--rcon-port", str(self.rcon_port)]),
            "--rcon-password", self.rcon_password,
            "--console-log", str(Path(self.log_path).with_name("console.log")),
            "--no-log-rotation",
        ]
        if self.server_settings:
            args += ["--server-settings", self.server_settings]
        if self.lua_udp_port:
            args += ["--enable-lua-udp", str(self.lua_udp_port)]
        if self.config:
            args += ["--config", self.config]
        return args

    def create_save(self, map_gen_settings: str | None = None,
                    map_settings: str | None = None,
                    extra: list[str] | None = None,
                    timeout: float = 600) -> None:
        """Create a fresh map with the same executable/mod directory."""
        args = [self.factorio_exe, "--create", self.save,
                "--mod-directory", self.mod_dir]
        if map_gen_settings:
            args += ["--map-gen-settings", map_gen_settings]
        if map_settings:
            args += ["--map-settings", map_settings]
        if extra:
            args += extra
        if self.config:
            args += ["--config", self.config]
        subprocess.run(args, check=True, timeout=timeout)

    def start(self) -> None:
        if self.proc and self.proc.poll() is None:
            return
        Path(self.log_path).parent.mkdir(parents=True, exist_ok=True)
        if self.config:
            cfg_dir = Path(self.config).parent
            (cfg_dir / "saves").mkdir(parents=True, exist_ok=True)
        self._log_handle = open(self.log_path, "w", encoding="utf-8", errors="replace")
        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.proc = subprocess.Popen(
            self.args(),
            stdin=subprocess.DEVNULL,
            stdout=self._log_handle,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
            cwd=str(Path(self.factorio_exe).parent),
        )

    def wait_ready(self, timeout: float = 60) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if _port_open("127.0.0.1", self.rcon_port):
                return
            if self.proc and self.proc.poll() is not None:
                raise RuntimeError(f"Factorio exited with code {self.proc.returncode}; see {self.log_path}")
            time.sleep(0.25)
        raise TimeoutError(f"RCON port {self.rcon_port} did not open within {timeout}s")

    def stop(self, save: bool = True, timeout: float = 20) -> None:
        """Save and gracefully quit the server via RCON."""
        if not self.proc:
            return
        if self.proc.poll() is None:
            try:
                from .rcon import RconClient, call_interface
                rc = RconClient("127.0.0.1", self.rcon_port, self.rcon_password, timeout=5).connect()
                if save:
                    try:
                        call_interface(rc, "agentbridge", "save")
                        time.sleep(1.5)
                    except Exception:
                        pass
                try:
                    rc.execute("/quit", timeout=3)
                except Exception:
                    pass
                rc.close()
            except Exception:
                pass
            try:
                self.proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
        if self._log_handle:
            self._log_handle.close()
            self._log_handle = None
        self.proc = None

    def tail(self, lines: int = 40) -> str:
        p = Path(self.log_path)
        if not p.exists():
            return ""
        return "\n".join(p.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])

    def __enter__(self):
        self.start()
        self.wait_ready()
        return self

    def __exit__(self, *exc):
        self.stop()
