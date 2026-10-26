"""Run a Lua snippet from a file through the live scenario eval interface.

Usage: python ops/run_lua.py ops/queries/survey.lua [--port 27017]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bridge.agent import AgentBridge  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("lua_file")
    ap.add_argument("--port", type=int, default=27017)
    ap.add_argument("--password", default="test")
    ap.add_argument("--pretty", action="store_true")
    ap.add_argument("--raw", action="store_true", help="print raw Lua result only")
    args = ap.parse_args()

    code = Path(args.lua_file).read_text(encoding="utf-8")
    b = AgentBridge(host="127.0.0.1", port=args.port, password=args.password)
    try:
        b.set_eval(True)
        res = b.lua_eval(code)
    finally:
        b.close()
    if args.raw and res.get("ok"):
        print(res.get("result", ""))
        return 0
    print(json.dumps(res, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
