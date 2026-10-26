"""Scripted end-to-end gameplay loop (no LLM): mine -> craft -> smelt -> take.

This is also a verification harness for the connector primitives.
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bridge.agent import AgentBridge
from bridge.server import FactorioServer

SERVER_KW = dict(
    factorio_exe=os.environ.get("FACTORIO_EXE") or str(ROOT / "standalone" / "bin" / "x64" / "factorio.exe"),
    save=str(ROOT / "server" / "lab.zip"),
    mod_dir=str(ROOT / "mods"),
    server_settings=str(ROOT / "server" / "lab-server-settings.json"),
    rcon_port=27016,
    rcon_password="test",
    lua_udp_port=35000,
    log_path=str(ROOT / "server" / "demo-stdout.log"),
)


def show(agent, label):
    print(f"\n=== {label}")
    print(agent.observe_text())


def main():
    srv = FactorioServer(**SERVER_KW)
    srv.start()
    srv.wait_ready()
    try:
        agent = AgentBridge()
        print("respawn:", agent.respawn(0, 0))
        show(agent, "fresh character")

        scan = agent.scan(96)
        names = {r["name"]: r for r in scan.get("resources", [])}
        print("resource types within 96:", {k: (round(v["nearest"]["distance"], 1), v.get("tiles"), v.get("total_amount")) for k, v in names.items()})

        for item, count in (("iron-ore", 10), ("stone", 5), ("coal", 5)):
            if item not in names:
                print(f"SKIP {item}: not found")
                continue
            r = agent.perform("mine", name=item, count=count, radius=96, timeout=300)
            print(f"mine {item}:", r.get("result"))
            show(agent, f"after mining {item}")

        st = agent.state()
        inv = {i["name"]: i["count"] for i in st["character"].get("inventory", [])}
        print("inventory:", inv)

        if inv.get("stone", 0) >= 5:
            r = agent.perform("craft", recipe="stone-furnace", count=1, timeout=60)
            print("craft furnace:", r.get("result"))
        if agent.state()["character"].get("inventory"):
            inv = {i["name"]: i["count"] for i in agent.state()["character"]["inventory"]}
        if inv.get("stone-furnace", 0) >= 1:
            pos = agent.state()["character"]["position"]
            r = agent.perform("place", name="stone-furnace",
                              x=round(pos["x"]) + 3, y=round(pos["y"]), timeout=30)
            print("place furnace:", r.get("result"))
            st = agent.state()
            furnaces = [e for e in st["entities"] if e["name"] == "stone-furnace"]
            if furnaces:
                uid = furnaces[0]["unit_number"]
                for item, n in (("coal", 5), ("iron-ore", 5)):
                    if inv.get(item, 0) >= n:
                        print(f"insert {item}:", agent.perform("insert", target=uid, item=item, count=n)["result"])
                    else:
                        print(f"SKIP insert {item}: have {inv.get(item, 0)}")
                print("wait:", agent.perform("wait", ticks=60 * 25, timeout=40).get("result"))
                print("take plates:", agent.perform("take", target=uid, item="iron-plate", count=10)["result"])
                show(agent, "after smelting")
        agent.save()
    finally:
        srv.stop(save=True)


if __name__ == "__main__":
    main()
