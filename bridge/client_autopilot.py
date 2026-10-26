#!/usr/bin/env python3
"""Unattended burner-era factory loop for a real Factorio client.

Repeats a small, safe tick using only normal client input (``ClientActions``):

1. collect ore from the chest placed on the burner drill's drop tile;
2. load the ore and some coal into the stone furnace;
3. collect smelted plates from the furnace;
4. share coal between the drill and the furnace;
5. hand-craft work orders that are below their target count;
6. walk back to the anchor position when straying.

Why time-based: entity inventories cannot be read through the client Lua
bridge (``get_inventory`` on a non-player entity hard-fails on this build), so
the loop schedules fuel by ticks and verifies progress through player
inventory deltas.  When a scenario/RCON observe channel is available, use it
alongside for true entity state.

All actions are normal player input; the server stays authoritative.  The
module can run standalone (``python -m bridge.client_autopilot``) or from the
client MCP server (``client_auto_start``).

Example::

    python -m bridge.client_autopilot --pid 1234 --name LLM-Bot \
        --minutes 6 --interval 20 \
        --drill -56,-2 --chest -56.5,-3.5 --furnace -49,6 --anchor -51,3 \
        --order "iron gear wheel=6" --coal 20
"""
from __future__ import annotations

import argparse
import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from .client_actions import ClientActions


@dataclass
class Layout:
    drill: tuple[float, float]
    chest: tuple[float, float]
    furnace: tuple[float, float]
    anchor: tuple[float, float] | None = None

    @classmethod
    def from_args(cls, args) -> "Layout":
        def point(text):
            x, y = str(text).split(",")
            return (float(x), float(y))

        return cls(drill=point(args.drill), chest=point(args.chest),
                   furnace=point(args.furnace),
                   anchor=point(args.anchor) if args.anchor else None)


@dataclass
class AutopilotStats:
    started_at: float = field(default_factory=time.time)
    ticks: int = 0
    errors: int = 0
    ore_collected: int = 0
    ore_loaded: int = 0
    plates_collected: int = 0
    coal_used: int = 0
    crafted: dict = field(default_factory=dict)
    last_tick: dict | None = None


class BurnerAutopilot:
    """A restartable, time-driven production loop over ClientActions."""

    def __init__(self, actions: ClientActions, layout: Layout,
                 coal_item: str = "coal", ore_item: str = "iron-ore",
                 plate_item: str = "iron-plate",
                 orders: dict[str, int] | None = None,
                 interval: float = 20.0, fuel_cycle: int = 4,
                 state_path: str | Path | None = None,
                 log=print):
        self.actions = actions
        self.layout = layout
        self.coal_item = coal_item
        self.ore_item = ore_item
        self.plate_item = plate_item
        self.orders = dict(orders or {})
        self.interval = float(interval)
        self.fuel_cycle = max(1, int(fuel_cycle))
        self.state_path = Path(state_path) if state_path else None
        self.log = log
        self.stats = AutopilotStats()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------- lifecycle
    def start(self, minutes: float | None = None) -> "BurnerAutopilot":
        if self._thread and self._thread.is_alive():
            raise RuntimeError("autopilot already running")
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, args=(minutes,), name="burner-autopilot", daemon=True)
        self._thread.start()
        return self

    def stop(self, join: float = 8.0) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(join)

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def status(self) -> dict:
        return {"running": self.running, "layout": {
            "drill": self.layout.drill, "chest": self.layout.chest,
            "furnace": self.layout.furnace, "anchor": self.layout.anchor},
            "orders": self.orders,
            "stats": self.stats.__dict__,
            "last_tick": self.stats.last_tick}

    # ------------------------------------------------------------------ loop
    def _run(self, minutes: float | None) -> None:
        deadline = time.time() + minutes * 60 if minutes else None
        self.log(f"autopilot start layout={self.layout} orders={self.orders} "
                 f"interval={self.interval}s")
        while not self._stop.is_set():
            if deadline and time.time() > deadline:
                self.log("autopilot reached the minute budget")
                break
            t0 = time.time()
            try:
                tick = self.tick()
                self.log(json.dumps(tick, ensure_ascii=False))
            except Exception as exc:  # keep the loop alive; report the tick
                self.stats.errors += 1
                self.log(f"autopilot tick error: {exc!r}")
            self._save()
            remain = self.interval - (time.time() - t0)
            if remain > 0 and self._stop.wait(remain):
                break
        self.log(f"autopilot stop {json.dumps(self.status()['stats'], ensure_ascii=False)}")
        self._save()

    def _save(self) -> None:
        if not self.state_path:
            return
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(
                json.dumps(self.status(), ensure_ascii=False, indent=1),
                encoding="utf-8")
        except OSError:
            pass

    # ------------------------------------------------------------------ tick
    def tick(self) -> dict:
        self.stats.ticks += 1
        n = self.stats.ticks
        actions = self.actions
        steps = {"tick": n, "t": round(time.time(), 1)}
        actions.close_all_ui()

        # 1) ore from the chest under the drill's drop tile
        try:
            out = actions.entity_take(self.layout.chest[0], self.layout.chest[1],
                                      "wooden-chest", "slot1")
            gained = out.get("gained", {}).get(self.ore_item, 0)
            self.stats.ore_collected += gained
            steps["ore_collected"] = gained
        except Exception as exc:
            steps["ore_error"] = str(exc)

        # 2) load whatever ore is held into the furnace
        held = actions.inventory_count(self.ore_item)
        if held:
            try:
                out = actions.entity_insert(self.layout.furnace[0], self.layout.furnace[1],
                                            "stone-furnace", self.ore_item, "input")
                moved = int(out.get("moved") or 0)
                self.stats.ore_loaded += moved
                steps["ore_loaded"] = moved
                if out.get("leftover_on_cursor"):
                    steps["ore_leftover"] = out["leftover_on_cursor"]
            except Exception as exc:
                steps["ore_load_error"] = str(exc)

        # 3) plates
        try:
            out = actions.entity_take(self.layout.furnace[0], self.layout.furnace[1],
                                      "stone-furnace", "output")
            gained = out.get("gained", {}).get(self.plate_item, 0)
            self.stats.plates_collected += gained
            steps["plates"] = gained
        except Exception as exc:
            steps["plate_error"] = str(exc)

        # 4) share coal: alternate drill / furnace, half a stack per insertion
        if n % (self.fuel_cycle * 2) == 1:
            steps["coal_drill"] = self._fuel(self.layout.drill, "burner-mining-drill")
        elif n % (self.fuel_cycle * 2) == 1 + self.fuel_cycle:
            steps["coal_furnace"] = self._fuel(self.layout.furnace, "stone-furnace")

        # 5) hand-craft work orders below target
        for query, target in self.orders.items():
            item = self._item_for_query(query)
            have = actions.inventory_count(item)
            if have < target:
                try:
                    out = actions.craft(query, 1, expect=item)
                    gained = out.get("gained", {})
                    if out.get("ok"):
                        steps.setdefault("crafted", {}).update(gained)
                        for k, v in gained.items():
                            self.stats.crafted[k] = self.stats.crafted.get(k, 0) + int(v)
                    else:
                        steps["craft_mismatch"] = gained
                except Exception as exc:
                    steps["craft_error"] = str(exc)
                break  # one craft per tick keeps the timing predictable

        # 6) stay near the machines
        anchor = self.layout.anchor
        if anchor:
            st = actions.state()
            px, py = st["pos"]["x"], st["pos"]["y"]
            if abs(px - anchor[0]) > 5 or abs(py - anchor[1]) > 5:
                try:
                    actions.walk_to(anchor[0], anchor[1], tolerance=3.0, timeout=90)
                    steps["walked_back"] = True
                except Exception as exc:
                    steps["walk_error"] = str(exc)

        self.stats.last_tick = steps
        return steps

    def _fuel(self, pos: tuple[float, float], entity: str) -> dict:
        if self.actions.inventory_count(self.coal_item) <= 0:
            return {"ok": False, "reason": f"no {self.coal_item}"}
        out = self.actions.entity_insert(pos[0], pos[1], entity,
                                         self.coal_item, "fuel", half=True)
        spent = max(0, int(out.get("moved") or 0))
        self.stats.coal_used += spent
        return {"ok": True, "coal_spent": spent}

    @staticmethod
    def _item_for_query(query: str) -> str:
        return {"iron gear wheel": "iron-gear-wheel",
                "iron gear": "iron-gear-wheel",
                "wooden chest": "wooden-chest",
                "transport belt": "transport-belt",
                "stone furnace": "stone-furnace",
                "burner mining drill": "burner-mining-drill"}.get(
                    query.lower().strip(), query.lower().replace(" ", "-"))


# --------------------------------------------------------------------- CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Unattended burner-era client loop")
    ap.add_argument("--pid", type=int, required=True)
    ap.add_argument("--name")
    ap.add_argument("--drill", required=True, help="x,y of the burner mining drill")
    ap.add_argument("--chest", required=True, help="x,y of the chest at its drop tile")
    ap.add_argument("--furnace", required=True, help="x,y of the stone furnace")
    ap.add_argument("--anchor", help="x,y to return to between ticks")
    ap.add_argument("--order", action="append", default=[],
                    help='craft work order "query=target", repeatable')
    ap.add_argument("--coal", type=int, default=0,
                    help="log how many coal the player starts with")
    ap.add_argument("--interval", type=float, default=20.0)
    ap.add_argument("--minutes", type=float, default=6.0)
    ap.add_argument("--state", default="state/autopilot_state.json")
    args = ap.parse_args(argv)

    orders = {}
    for raw in args.order:
        query, _, target = raw.partition("=")
        orders[query.strip()] = int(target or 1)

    actions = ClientActions(args.pid, args.name)
    try:
        st = actions.state()
        print(f"start at {st['pos']} controller={st.get('controller')} "
              f"inventory={st.get('inventory')}")
        if args.coal:
            print(f"coal in inventory: {actions.inventory_count('coal')}")
        auto = BurnerAutopilot(actions, Layout.from_args(args), orders=orders,
                               interval=args.interval,
                               state_path=args.state,
                               log=lambda msg: print(msg, flush=True))
        auto.start(args.minutes)
        while auto.running:
            time.sleep(1.0)
        return 0
    finally:
        actions.close()


if __name__ == "__main__":
    raise SystemExit(main())
