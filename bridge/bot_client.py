"""Launch and supervise a second, real Factorio client as the bot's body.

The bot must be a real player for other players to see it and for LuaPlayer
APIs (blueprints, space platforms, GUIs) to exist.  A server-side mod cannot
create a LuaPlayer.

This supervisor expects a standalone Factorio client.  The Steam build is not
suitable for a second concurrent instance (Steam app/account single-instance);
it is rejected by default when steam_api64.dll sits next to the executable.
Use a standalone build for the bot body, with a separate --config, mod dir and
local UDP port.  See docs/COEXISTENCE.md.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILTIN_MODS = {"base", "core", "elevated-rails", "quality", "recycler", "space-age"}


def sync_mods(source: str, target: str) -> dict:
    """Mirror enabled non-builtin mods from a Factorio mod directory.

    The human Steam profile often has a different mod set from the bot.  A
    second client must load exactly the server's enabled mods, so this copies
    only enabled mod zips/directories and writes a matching mod-list.json.
    Built-in base/DLC mods are kept as entries but have no files to copy.
    """
    src, dst = Path(source), Path(target)
    if not (src / "mod-list.json").exists():
        raise RuntimeError(f"no mod-list.json in {src}")
    if src.resolve() == dst.resolve():
        return {"ok": True, "copied": [], "source": str(src), "target": str(dst)}
    dst.mkdir(parents=True, exist_ok=True)
    try:
        incoming = json.loads((src / "mod-list.json").read_text(encoding="utf-8"))
    except Exception as e:
        raise RuntimeError(f"cannot read {src / 'mod-list.json'}: {e}")
    enabled = [m.get("name") for m in incoming.get("mods", []) if m.get("enabled")]
    enabled = [n for n in enabled if n]
    copied, missing = [], []
    # Canonical order first, then the source's non-builtin enabled mods.
    ordered = ["base", "elevated-rails", "quality", "recycler", "space-age"]
    for name in enabled:
        if name not in ordered:
            ordered.append(name)
    out_mods = [{"name": name, "enabled": True} for name in ordered]
    for name in enabled:
        if name in BUILTIN_MODS:
            continue
        src_zip = sorted(src.glob(f"{name}_*.zip"))
        src_dir = src / name
        if src_zip:
            dst_zip = dst / src_zip[-1].name
            if not dst_zip.exists() or dst_zip.stat().st_size != src_zip[-1].stat().st_size:
                shutil.copy2(src_zip[-1], dst_zip)
            copied.append(dst_zip.name)
        elif src_dir.is_dir():
            dt = dst / name
            if dt.exists():
                shutil.rmtree(dt)
            shutil.copytree(src_dir, dt)
            copied.append(name + "/")
        else:
            missing.append(name)
    (dst / "mod-list.json").write_text(
        json.dumps({"mods": out_mods}, ensure_ascii=False, indent=2), encoding="utf-8")
    if missing:
        raise RuntimeError(f"enabled mods not found in {src}: {', '.join(missing)}")
    return {"ok": True, "copied": copied, "source": str(src), "target": str(dst),
            "mods": [m["name"] for m in out_mods]}


class BotClient:
    def __init__(self, factorio_exe: str, server_host: str = "127.0.0.1",
                 server_port: int = 34197, player_name: str = "LLM-Bot",
                 data_dir: str | None = None, mod_dir: str | None = None,
                 window_size: str = "800x600", minimize: bool = True,
                 log_path: str | None = None,
                 read_data: str | None = None,
                 client_port: int | None = 34198,
                 bind: str | None = None,
                 allow_steam: bool = False):
        self.exe = str(Path(factorio_exe).expanduser().resolve())
        exe_dir = Path(self.exe).resolve().parent
        # Two Steam clients for the same app/account are not supported. The
        # standalone build has no steam_api64.dll and is the supported body.
        if not allow_steam and (exe_dir / "steam_api64.dll").exists():
            raise RuntimeError(
                "this looks like a Steam Factorio build (steam_api64.dll next to the exe); "
                "use a standalone Factorio client for the second instance, or pass --allow-steam "
                "only if you know your Steam setup supports a second instance")
        self.host = server_host
        self.port = server_port
        self.client_port = client_port
        self.bind = bind
        self.player_name = player_name
        self.data_dir = Path(data_dir or ROOT / "bot-data").expanduser().resolve()
        self.mod_dir = str(Path(mod_dir or ROOT / "server" / "scenario-mods").expanduser().resolve())
        self.window_size = window_size
        self.minimize = minimize
        self.log_path = Path(log_path or ROOT / "server" / "bot-client.log").expanduser().resolve()
        root = Path(self.exe).resolve().parents[2]
        candidate = root / "data"
        self.read_data = str(Path(read_data).expanduser().resolve()) if read_data else str(candidate if candidate.exists() else root)
        self.proc: subprocess.Popen | None = None
        self._log = None

    # -- configuration ------------------------------------------------------
    def config_path(self) -> Path:
        return self.data_dir / "config.ini"

    def prepare(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config_path().write_text(
            "[path]\n"
            f"write-data={self.data_dir.as_posix()}\n"
            f"read-data={Path(self.read_data).as_posix()}\n"
            "\n[general]\n"
            "locale=en\n"
            "\n[other]\n"
            "autosave-interval=0\n",
            encoding="utf-8",
        )
        player = self.data_dir / "player-data.json"
        if not player.exists():
            player.write_text(json.dumps({
                "username": self.player_name,
                "service-username": self.player_name,
                "service-token": "",
            }, indent=2), encoding="utf-8")

    # -- lifecycle ----------------------------------------------------------
    def args(self) -> list[str]:
        args = [
            self.exe,
            "--mp-connect", f"{self.host}:{self.port}",
            "--config", str(self.config_path()),
            "--mod-directory", self.mod_dir,
            "--window-size", self.window_size,
            "--graphics-quality", "low",
            "--force-graphics-preset", "very-low",
            "--max-texture-size", "2048",
            "--disable-audio",
            "--no-log-rotation",
            "--nogamepad",
        ]
        # Factorio clients normally use an ephemeral UDP port. Binding an
        # explicit second port avoids collisions with a locally hosted server
        # or the human Steam client on 34197.
        if self.client_port:
            args += ["--port", str(self.client_port)]
        if self.bind:
            args += ["--bind", self.bind]
        return args

    def start(self) -> None:
        self.prepare()
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log = open(self.log_path, "w", encoding="utf-8", errors="replace")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        # A real client needs a window; CREATE_NO_WINDOW is used only for the
        # supervisor console, not the game window.  Factorio creates its own.
        self.proc = subprocess.Popen(self.args(), stdin=subprocess.DEVNULL,
                                     stdout=self._log, stderr=subprocess.STDOUT,
                                     cwd=str(Path(self.exe).parent))
        if self.minimize:
            self._minimize_when_ready()

    def _window_handle(self):
        if os.name != "nt" or not self.proc:
            return None
        target = self.proc.pid
        result = []
        EnumProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

        def cb(hwnd, _):
            pid = wt.DWORD()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == target and ctypes.windll.user32.IsWindowVisible(hwnd):
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                if length:
                    result.append(hwnd)
            return True

        ctypes.windll.user32.EnumWindows(EnumProc(cb), 0)
        return result[0] if result else None

    def _minimize_when_ready(self, timeout: float = 30) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            hwnd = self._window_handle()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
                return
            time.sleep(0.5)

    def wait_connected(self, bridge=None, timeout: float = 180) -> dict:
        """Wait until the scenario sees this player connected (or the log says InGame)."""
        deadline = time.time() + timeout
        last = {}
        while time.time() < deadline:
            if self.proc and self.proc.poll() is not None:
                raise RuntimeError(f"bot client exited with {self.proc.returncode}; see {self.log_path}")
            if bridge is not None:
                try:
                    last = bridge.state()
                    p = last.get("player") or {}
                    if p.get("connected") and p.get("name") == self.player_name:
                        return last
                except Exception:
                    pass
            if self.log_path.exists():
                text = self.log_path.read_text(encoding="utf-8", errors="replace")
                if "changing state from(WaitingForCommandToStartSendingTickClosures) to(InGame)" in text:
                    return last
            time.sleep(1.0)
        raise TimeoutError(f"bot player {self.player_name!r} did not connect within {timeout}s; see {self.log_path}")

    def stop(self, timeout: float = 10) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        if self._log:
            self._log.close()
            self._log = None
        self.proc = None

    def tail(self, lines: int = 40) -> str:
        p = self.log_path
        if not p.exists():
            return ""
        return "\n".join(p.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])


def main(argv=None) -> None:
    """CLI entry point for launching the real second Factorio client.

    Examples:
        python -m bridge.bot_client --exe "C:/Factorio/bin/x64/factorio.exe" --wait
        python -m bridge.bot_client --exe ... --server 127.0.0.1:34197 --name LLM-Bot
    """
    import argparse

    ap = argparse.ArgumentParser(description="Launch the real Factorio client used as the LLM bot's body")
    ap.add_argument("--exe", default=os.environ.get("FACTORIO_CLIENT_EXE") or os.environ.get("FACTORIO_EXE"),
                    help="standalone Factorio client executable (not the Steam build for a second instance)")
    ap.add_argument("--server", default="127.0.0.1:34197", help="host:port of the game server")
    ap.add_argument("--name", default="LLM-Bot", help="in-game player name")
    ap.add_argument("--data-dir", default=None, help="writable client data dir (default: bot-data)")
    ap.add_argument("--mod-dir", default=None, help="client mod dir (default: server/scenario-mods)")
    ap.add_argument("--window-size", default="800x600")
    ap.add_argument("--client-port", type=int, default=34198,
                    help="local UDP port for the second client (default 34198; 34197 is the server)")
    ap.add_argument("--bind", help="optional local bind address, e.g. 0.0.0.0:34198")
    ap.add_argument("--mod-source", help="copy enabled mods from another Factorio mod directory before launch")
    ap.add_argument("--allow-steam", action="store_true", help="allow launching the Steam build (not recommended)")
    ap.add_argument("--no-minimize", action="store_true")
    ap.add_argument("--wait", action="store_true", help="wait until the scenario reports this player connected")
    ap.add_argument("--timeout", type=float, default=180.0)
    ap.add_argument("--rcon-host", default="127.0.0.1")
    ap.add_argument("--rcon-port", type=int, default=27017)
    ap.add_argument("--rcon-password", default="test")
    a = ap.parse_args(argv)

    if not a.exe:
        ap.error("--exe is required (or set FACTORIO_CLIENT_EXE / FACTORIO_EXE)")
    host, _, port_s = a.server.rpartition(":")
    if not host:
        host, port_s = a.server, "34197"
    try:
        port = int(port_s)
    except ValueError:
        ap.error("--server must be host:port, e.g. 127.0.0.1:34197")

    if a.mod_source:
        sync_mods(a.mod_source, a.mod_dir or str(ROOT / "server" / "scenario-mods"))
    bc = BotClient(
        factorio_exe=a.exe, server_host=host, server_port=port,
        player_name=a.name, data_dir=a.data_dir, mod_dir=a.mod_dir,
        window_size=a.window_size, minimize=not a.no_minimize,
        client_port=a.client_port, bind=a.bind, allow_steam=a.allow_steam,
    )
    bc.start()
    print(f"client started: pid={bc.proc.pid if bc.proc else '?'} name={a.name} server={host}:{port}")
    print(f"client log: {bc.log_path}")
    if a.wait:
        from .agent import AgentBridge
        br = AgentBridge(a.rcon_host, a.rcon_port, a.rcon_password)
        try:
            st = bc.wait_connected(br, timeout=a.timeout)
            p = st.get("player") or {}
            print(f"bot player connected: {p.get('name')} at {p.get('physical_position')}")
        finally:
            br.close()


if __name__ == "__main__":
    main()
