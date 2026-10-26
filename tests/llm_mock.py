"""Verify the LLM tool-calling loop without calling a real model."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge.agent import AgentBridge
from bridge.llm_agent import LLMAgent
from bridge.server import FactorioServer

KW = dict(
    factorio_exe=os.environ.get("FACTORIO_EXE") or str(ROOT / "standalone" / "bin" / "x64" / "factorio.exe"),
    save=str(ROOT / "server" / "lab.zip"), mod_dir=str(ROOT / "mods"),
    server_settings=str(ROOT / "server" / "lab-server-settings.json"),
    rcon_port=27016, rcon_password="test",
    log_path=str(ROOT / "server" / "llm-mock-stdout.log"),
)

srv = FactorioServer(**KW)
srv.start(); srv.wait_ready()
try:
    br = AgentBridge()
    agent = LLMAgent(br, api_key="fake", log_path=ROOT / "state" / "llm-mock.jsonl")
    responses = [
        {"choices": [{"message": {"role": "assistant", "content": "", "tool_calls": [
            {"id": "call1", "type": "function",
             "function": {"name": "observe", "arguments": "{}"}}]}}]},
        {"choices": [{"message": {"role": "assistant", "content": "I will move.", "tool_calls": [
            {"id": "call2", "type": "function",
             "function": {"name": "walk_to", "arguments": "{\"x\":12,\"y\":-18}"}}]}}]},
        {"choices": [{"message": {"role": "assistant", "content": "done"}}]},
    ]
    agent._post = lambda payload: responses.pop(0)
    result = agent.run("test mock", max_turns=5, turn_based=True, verbose=False)
    print("result:", result)
    print("paused after run:", br.state().get("paused"))
    assert result == "done"
    assert br.state().get("paused") is False
    br.close()
finally:
    srv.stop(save=True)
