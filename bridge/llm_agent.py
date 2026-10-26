"""OpenAI-compatible tool-calling loop with local and cloud model providers.

Providers:
  provider=local  use LOCAL_LLM_BASE_URL / LOCAL_LLM_MODEL (no key required)
  provider=cloud  use OPENAI_BASE_URL / OPENAI_API_KEY / OPENAI_MODEL
  provider=auto   prefer a configured local endpoint, optionally fall back to cloud

Local deployments that speak the OpenAI API work directly:
  Ollama      http://127.0.0.1:11434/v1
  LM Studio   http://127.0.0.1:1234/v1
  llama.cpp   http://127.0.0.1:8080/v1
  vLLM        http://127.0.0.1:8000/v1
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

from .agent import AgentBridge, TOOL_SCHEMAS, format_observation

SYSTEM_PROMPT = """You are an embodied engineer in Factorio. You control one real player in a
multiplayer server. The character has a body, an inventory, and must obey the game's normal
rules: it walks with collision, mines at the game's mining speed, hand-crafts with real
ingredients and crafting time, places buildings with real validation, and uses real furnaces.

Rules:
- Never invent coordinates or items. Call `observe` or `scan` first.
- Work one action at a time. A tool call blocks until the action finishes or fails.
- If a job fails, read its `detail`, adapt, and try a different position/recipe.
- Resource names are Factorio prototype names (iron-ore, copper-ore, coal, stone, ...).
- Directions: 0=north, 4=east, 8=south, 12=west; diagonals are 2,6,10,14.
- Do not claim success unless a tool result says ok/done. Report progress briefly.
- Prefer realistic play: mine, smelt, craft, build, research, automate. Avoid cheats.
- Use `mine(resource="tree")` to chop trees for wood; rocks/trees are not in the
  resource list. Use `find_water` before planning steam power.
- Early power: an offshore-pump must sit on water; place a boiler next to it and a
  steam engine next to the boiler, then connect a small electric pole to the engine
  and the lab. Pipes/poles auto-connect when placed adjacent/in range.
- Early research: craft a lab, supply it with red science (copper plate + iron gear),
  and queue technologies with `research`. Green science is unlocked by researching
  `logistic-science-pack` (75 red science).
- For repeated structures use `blueprint_create` then `blueprint_build`. Modes:
  `cost` (default) instantly builds and consumes matching items from the inventory,
  `ghost` only places construction ghosts, `force` builds without materials (avoid
  unless the operator asks). Missing/blocked placements return an explicit error.
- For Space Age use `space` actions (create/apply_starter_pack/enter/leave/land/pause/
  resume/schedule/go/add_stop/clear_schedule/hub) and build on the platform surface.
  `land` waits for the engine descent (several seconds) before returning.
- `lua_eval` is a last-resort API escape hatch and is disabled unless the operator enables it.

Your job is to make progress on the user's task, not to describe Factorio in general."""


def _compact_tool_result(text: str) -> str:
    """Shrink repetitive state/scan payloads before they enter the model context."""
    try:
        data = json.loads(text)
    except Exception:
        return text
    if not isinstance(data, dict):
        return text
    changed = False
    state = data.get("state")
    if isinstance(state, dict):
        data.pop("state", None)
        data["observation"] = format_observation(state)
        changed = True
    for key, limit in (("resources", 12), ("entities", 30), ("technologies", 20),
                       ("blueprints", 20), ("platforms", 10)):
        value = data.get(key)
        if isinstance(value, list) and len(value) > limit:
            data[key] = value[:limit]
            data[key + "_truncated"] = len(value) - limit
            changed = True
    return json.dumps(data, ensure_ascii=False) if changed else text


class LLMAgent:
    def __init__(self, bridge: AgentBridge | None = None,
                 api_key: str | None = None,
                 base_url: str | None = None,
                 model: str | None = None,
                 log_path: str | Path | None = None,
                 llm_settings: dict | None = None,
                 event_log: str | Path | None = None,
                 event_cb: Callable[[dict], None] | None = None):
        self.bridge = bridge or AgentBridge()
        s = llm_settings or {}
        self.local_base = (s.get("local_base_url") or os.environ.get("LOCAL_LLM_BASE_URL", "")).rstrip("/")
        self.local_model = s.get("local_model") or os.environ.get("LOCAL_LLM_MODEL", "")
        self.local_key = s.get("local_api_key") or os.environ.get("LOCAL_LLM_API_KEY", "") or "local"
        self.cloud_base = (base_url or s.get("cloud_base_url") or os.environ.get("OPENAI_BASE_URL")
                           or "https://api.openai.com/v1").rstrip("/")
        self.cloud_model = model or s.get("cloud_model") or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        self.cloud_key = api_key or s.get("cloud_api_key") or os.environ.get("OPENAI_API_KEY", "")
        self.provider_mode = (s.get("provider") or os.environ.get("LLM_PROVIDER", "auto")).lower()
        self.fallback_cloud = bool(s.get("fallback_cloud", True))
        self.temperature = float(s.get("temperature", 0.2))
        self._log_path = Path(log_path) if log_path else None
        self._log_handle = None
        self._event_path = Path(event_log) if event_log else None
        self._event_handle = None
        self._event_cb = event_cb
        self._fallback_used = False
        self.last_summary = ""
        self._select_provider()

    # -- provider selection -------------------------------------------------

    def _select_provider(self) -> None:
        local_ready = bool(self.local_base and self.local_model)
        cloud_ready = bool(self.cloud_base and self.cloud_model)
        if self.provider_mode == "local":
            if not local_ready:
                raise RuntimeError("LLM provider=local but LOCAL_LLM_BASE_URL/LOCAL_LLM_MODEL are not set")
            self.active_provider = "local"
        elif self.provider_mode == "cloud":
            self.active_provider = "cloud"
        else:
            self.active_provider = "local" if local_ready else "cloud"
        self._apply_provider()

    def _apply_provider(self) -> None:
        if self.active_provider == "local":
            self.base_url, self.model, self.api_key = self.local_base, self.local_model, self.local_key
        else:
            self.base_url, self.model, self.api_key = self.cloud_base, self.cloud_model, self.cloud_key

    @property
    def describe(self) -> dict:
        return {"provider": self.active_provider, "model": self.model, "base_url": self.base_url,
                "fallback_cloud": self.fallback_cloud, "fallback_used": self._fallback_used}

    # -- HTTP ---------------------------------------------------------------

    def _http(self, payload: dict) -> dict:
        if not self.base_url:
            raise RuntimeError("LLM base URL is empty")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            raise RuntimeError(f"LLM HTTP {e.code}: {body[:800]}") from e
        except Exception as e:
            raise RuntimeError(f"LLM request failed ({self.base_url}): {e}") from e

    def _post(self, payload: dict) -> dict:
        try:
            return self._http(payload)
        except Exception as e:
            if (self.active_provider == "local" and self.fallback_cloud
                    and self.cloud_base and self.cloud_model):
                self._emit("provider_fallback", {"from": "local", "to": "cloud", "error": str(e)})
                self.active_provider = "cloud"
                self._fallback_used = True
                self._apply_provider()
                return self._http(payload)
            raise

    @staticmethod
    def list_models(base_url: str, api_key: str = "", timeout: float = 15) -> dict:
        """Query OpenAI-compatible /models, with an Ollama /api/tags fallback."""
        base = (base_url or "").rstrip("/")
        if not base:
            return {"ok": False, "error": "base URL is empty"}
        headers = {}
        if api_key and api_key != "local":
            headers["Authorization"] = f"Bearer {api_key}"
        candidates = [base + "/models"]
        if base.endswith("/v1"):
            candidates.append(base[:-3] + "/api/tags")
        last = None
        for url in candidates:
            try:
                req = urllib.request.Request(url, headers=headers, method="GET")
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                if isinstance(data, dict) and "data" in data:
                    models = [m.get("id") for m in data.get("data", []) if isinstance(m, dict)]
                elif isinstance(data, dict) and "models" in data:
                    models = [m.get("name") for m in data.get("models", []) if isinstance(m, dict)]
                else:
                    models = []
                return {"ok": True, "models": models, "source": url}
            except Exception as e:
                last = str(e)
        return {"ok": False, "error": last or "no model endpoint"}

    # -- event/log plumbing -------------------------------------------------

    def _emit(self, kind: str, data: dict) -> None:
        record = {"ts": time.time(), "type": kind, **data}
        if self._event_path:
            self._event_path.parent.mkdir(parents=True, exist_ok=True)
            if not self._event_handle:
                self._event_handle = open(self._event_path, "a", encoding="utf-8")
            self._event_handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            self._event_handle.flush()
        if self._event_cb:
            try:
                self._event_cb(record)
            except Exception:
                pass

    def _log(self, record: dict) -> None:
        if not self._log_path:
            return
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        if not self._log_handle:
            self._log_handle = open(self._log_path, "a", encoding="utf-8")
        self._log_handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._log_handle.flush()

    def close(self) -> None:
        for h in (self._log_handle, self._event_handle):
            if h:
                try:
                    h.close()
                except Exception:
                    pass
        self._log_handle = None
        self._event_handle = None

    # -- loop ---------------------------------------------------------------

    def run(self, task: str, max_turns: int = 25, turn_based: bool = False,
            verbose: bool = True) -> str:
        self.last_summary = ""
        state = self.bridge.state()
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": task + "\n\nCurrent observation:\n" + format_observation(state)},
        ]
        self._emit("cycle_start", {"task": task[:4000], "observation": format_observation(state),
                                   "provider": self.active_provider, "model": self.model})
        final_text = ""
        try:
            if turn_based:
                self.bridge.pause(True)
            final_text = self._loop(task, messages, max_turns, turn_based, verbose)
        finally:
            if turn_based:
                self.bridge.pause(False)
            self._emit("cycle_end", {"text": final_text, "provider": self.active_provider})
        return final_text

    def _loop(self, task, messages, max_turns, turn_based, verbose) -> str:
        final_text = ""
        actions = []
        for turn in range(max_turns):
            try:
                response = self._post({
                    "model": self.model,
                    "messages": messages,
                    "tools": TOOL_SCHEMAS,
                    "tool_choice": "auto",
                    "temperature": self.temperature,
                })
            except Exception as e:
                self._emit("error", {"error": str(e), "turn": turn, "provider": self.active_provider})
                raise
            choice = (response.get("choices") or [{}])[0]
            msg = choice.get("message") or {}
            content = msg.get("content") or ""
            reasoning = (msg.get("reasoning_content") or msg.get("reasoning")
                         or msg.get("thinking") or "")
            tool_calls = msg.get("tool_calls") or []
            messages.append({"role": "assistant", "content": content,
                             **({"tool_calls": tool_calls} if tool_calls else {})})
            self._log({"turn": turn, "assistant": content, "tool_calls": tool_calls})
            self._emit("assistant", {"turn": turn, "content": content, "reasoning": reasoning,
                                     "tool_calls": tool_calls, "provider": self.active_provider,
                                     "model": self.model})
            if verbose and content:
                print(f"\n[assistant] {content}")
            if not tool_calls:
                if content:
                    final_text = content
                elif reasoning:
                    final_text = "(model ended with reasoning only)"
                else:
                    final_text = "(empty response)"
                break

            for call in tool_calls:
                fn = call.get("function") or {}
                name = fn.get("name") or ""
                raw_args = fn.get("arguments") or "{}"
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except json.JSONDecodeError:
                    args = {}
                read_only = name in ("observe", "scan", "recipe_info", "technologies", "blueprints")
                if turn_based and not read_only:
                    self.bridge.resume()
                try:
                    result = self.bridge.execute_tool(name, args)
                    result = _compact_tool_result(result)
                except Exception as e:
                    result = json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"})
                if turn_based and not read_only:
                    # Freeze the world again while the model thinks about the result.
                    self.bridge.pause(True)
                if verbose:
                    print(f"[tool] {name}({raw_args}) -> {result[:600]}")
                messages.append({"role": "tool", "tool_call_id": call.get("id", ""),
                                 "content": result})
                self._emit("tool_call", {"turn": turn, "name": name, "args": args,
                                         "call_id": call.get("id", "")})
                self._emit("tool_result", {"turn": turn, "name": name,
                                           "result": result[:12000]})
                self._log({"turn": turn, "tool": name, "args": args, "result": result})
                try:
                    parsed = json.loads(result)
                    payload = parsed.get("result") if isinstance(parsed, dict) else None
                    ok = bool(parsed.get("ok")) if isinstance(parsed, dict) else False
                    if isinstance(payload, dict):
                        ok = ok or bool(payload.get("ok"))
                    detail = ""
                    if isinstance(payload, dict):
                        detail = str(payload.get("detail") or "")
                    if isinstance(parsed, dict) and parsed.get("error"):
                        detail = str(parsed.get("error"))
                    if not detail:
                        detail = result[:180]
                except Exception:
                    ok, detail = False, result[:180]
                actions.append(f"{name}({json.dumps(args, ensure_ascii=False)}) -> "
                               f"{'ok' if ok else 'fail'}: {detail[:220]}")
        self.last_summary = " | ".join(actions[-16:])
        if not final_text:
            final_text = "(max turns reached)"
        return final_text
