"""Continue from a saved lab: walk to the existing furnace, smelt iron, take plates."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge.agent import AgentBridge
from bridge.server import FactorioServer

KW = dict(
    factorio_exe=os.environ.get("FACTORIO_EXE") or str(ROOT / "standalone" / "bin" / "x64" / "factorio.exe"),
    save=str(ROOT / "server" / "lab.zip"), mod_dir=str(ROOT / "mods"),
    server_settings=str(ROOT / "server" / "lab-server-settings.json"),
    rcon_port=27016, rcon_password="test", lua_udp_port=35000,
    log_path=str(ROOT / "server" / "smelt-stdout.log"),
)

srv = FactorioServer(**KW)
srv.start(); srv.wait_ready()
try:
    a = AgentBridge()
    print(a.observe_text())
    print("walk:", a.perform("walk", x=12, y=-18, timeout=180).get("result"))
    print(a.observe_text())
    st = a.state()
    inv = {i["name"]: i["count"] for i in st["character"]["inventory"]}
    print("inventory:", inv)
    furnaces = [e for e in st["entities"] if e["name"] == "stone-furnace"]
    print("furnaces:", furnaces)
    if furnaces:
        uid = furnaces[0]["unit_number"]
        for item, n in (("coal", 5), ("iron-ore", 5)):
            have = inv.get(item, 0)
            if have >= n:
                print(f"insert {item}:", a.perform("insert", target=uid, item=item, count=n).get("result"))
            else:
                print(f"skip {item}, have {have}")
        print("wait:", a.perform("wait", ticks=60 * 28, timeout=45).get("result"))
        print("take iron plate:", a.perform("take", target=uid, item="iron-plate", count=10).get("result"))
        print("take copper plate:", a.perform("take", target=uid, item="copper-plate", count=10).get("result"))
        print(a.observe_text())
    a.save()
finally:
    srv.stop(save=True)
