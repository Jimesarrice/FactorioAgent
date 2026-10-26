"""Minimal Factorio 2.x blueprint string encoder/decoder.

Entity positions are tile centres relative to the blueprint origin.  The game
normalises the bounding box when the blueprint is built, so coordinates may be
given as small positive numbers (0.5, 1.5, ...).
"""
from __future__ import annotations

import base64
import json
import zlib
from typing import Any

VERSION = 562954249895938


def encode(blueprint: dict[str, Any], version: int = VERSION) -> str:
    bp = dict(blueprint)
    bp.setdefault("item", "blueprint")
    bp.setdefault("version", version)
    raw = json.dumps({"blueprint": bp}, separators=(",", ":")).encode("utf-8")
    return "0" + base64.b64encode(zlib.compress(raw, 9)).decode("ascii")


def decode(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("0"):
        text = text[1:]
    return json.loads(zlib.decompress(base64.b64decode(text)).decode("utf-8"))


def entity(number: int, name: str, x: float, y: float, direction: int | None = None,
           recipe: str | None = None, **extra: Any) -> dict[str, Any]:
    e: dict[str, Any] = {"entity_number": number, "name": name,
                         "position": {"x": x, "y": y}}
    if direction:
        e["direction"] = direction
    if recipe:
        e["recipe"] = recipe
    e.update(extra)
    return e
