"""Start a second real client (Watcher) and verify multi-client visibility."""
import os, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge.bot_client import BotClient
from bridge.rcon import RconClient

client = BotClient(os.environ.get("FACTORIO_CLIENT_EXE") or os.environ.get("FACTORIO_EXE") or str(Path(__file__).resolve().parents[1] / "standalone" / "bin" / "x64" / "factorio.exe"), "127.0.0.1", 34197, "Watcher",
                   data_dir=str(ROOT / "watcher-data"),
                   mod_dir=str(ROOT / "server" / "scenario-mods"),
                   minimize=True, log_path=str(ROOT / "server" / "watcher-client.log"))
print("args:", client.args(), flush=True)
client.start()
rc = RconClient("127.0.0.1", 27017, "test").connect()
for _ in range(2):
    rc.execute('/c rcon.print("warm")')
deadline = time.time() + 180
while time.time() < deadline:
    try:
        names = rc.execute('/c local t={}; for _,p in pairs(game.connected_players) do table.insert(t,p.name) end; rcon.print(table.concat(t,","))').strip()
    except Exception as e:
        names = "ERR " + str(e)
    print("players:", names, flush=True)
    if "Watcher" in names:
        print("WATCHER_CONNECTED", names, flush=True)
        break
    if client.proc and client.proc.poll() is not None:
        print("WATCHER_EXITED", client.proc.returncode, flush=True)
        break
    time.sleep(2)
print("LOG\n" + client.tail(80), flush=True)
print("HOLDING", flush=True)
time.sleep(900)
