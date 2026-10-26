"""Start the real bot client, wait for the scenario to see the player, then hold."""
import os, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge.bot_client import BotClient
from bridge.agent import AgentBridge

exe = os.environ.get("FACTORIO_CLIENT_EXE") or os.environ.get("FACTORIO_EXE") or str(Path(__file__).resolve().parents[1] / "standalone" / "bin" / "x64" / "factorio.exe")
client = BotClient(exe, "127.0.0.1", 34197, "LLM-Bot",
                   data_dir=str(ROOT / "bot-data"),
                   mod_dir=str(ROOT / "server" / "scenario-mods"),
                   minimize=True, log_path=str(ROOT / "server" / "bot-client.log"))
print("args:", client.args(), flush=True)
client.start()
bridge = AgentBridge(port=27017)
try:
    st = client.wait_connected(bridge, timeout=180)
    print("CONNECTED", st.get("player"), flush=True)
    print("OBSERVE\n" + bridge.observe_text(), flush=True)
except Exception as e:
    print("WAIT_FAILED", type(e).__name__, e, flush=True)
    print("LOG\n" + client.tail(120), flush=True)
finally:
    bridge.close()
print("HOLDING", flush=True)
time.sleep(900)
