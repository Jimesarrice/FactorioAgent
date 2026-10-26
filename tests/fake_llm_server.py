"""Tiny OpenAI-compatible fake for local-provider/web-UI smoke tests."""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODEL = "fake-local"


class H(BaseHTTPRequestHandler):
    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.rstrip("/").endswith("/models"):
            return self._json({"object": "list", "data": [{"id": MODEL, "object": "model"}]})
        self.send_error(404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        self._json({"id": "fake", "object": "chat.completion", "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "本地假模型：收到观察，当前保持待命；下一步会先确认资源与背包。",
                "reasoning_content": "这是 fake-local 返回的 reasoning 字段，用于验证 Web 控制台的思维链/决策日志渲染。",
            },
            "finish_reason": "stop",
        }]})

    def log_message(self, fmt, *args):
        print("[fake-llm]", fmt % args, flush=True)


if __name__ == "__main__":
    print("fake LLM on 127.0.0.1:11435", flush=True)
    ThreadingHTTPServer(("127.0.0.1", 11435), H).serve_forever()
