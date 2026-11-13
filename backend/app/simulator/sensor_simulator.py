from __future__ import annotations

import asyncio
import math
import random
from datetime import datetime, timezone
from typing import Callable

from app.schemas import Reading

ZONES = [
    {"id": "north_wall", "name": "North Wall", "x": 29, "y": 24},
    {"id": "east_bench", "name": "East Bench", "x": 71, "y": 43},
    {"id": "south_ramp", "name": "South Ramp", "x": 43, "y": 76},
]


class Simulator:
    def __init__(self, submit: Callable[[Reading], None], interval: float = 5) -> None:
        self.submit = submit
        self.interval = interval
        self.scenario = "normal"
        self.tick = 0
        self.task: asyncio.Task | None = None

    @property
    def running(self) -> bool:
        return self.task is not None and not self.task.done()

    def status(self) -> dict:
        return {"running": self.running, "scenario": self.scenario, "interval_seconds": self.interval, "source": "simulated"}

    def reading(self, zone_id: str) -> Reading:
        t = self.tick
        phase = {"north_wall": 0, "east_bench": 1.2, "south_ramp": 2.4}[zone_id]
        noise = random.Random(f"{zone_id}-{t}").uniform(-0.6, 0.6)
        rain = 2 + 1.5 * math.sin(t / 5 + phase)
        displacement = 2 + 0.25 * math.sin(t / 7 + phase)
        if self.scenario == "heavy_rain":
            rain += min(t * 2.8, 55)
        if self.scenario == "slope_movement":
            displacement += min(t * 1.35, 28)
        moisture = min(95, 34 + max(0, rain - 2) * 0.85 + noise)
        strain = min(90, 20 + displacement * 2.4 + noise)
        vibration = min(14, 1.2 + displacement * 0.3 + abs(noise))
        return Reading(zone_id=zone_id, timestamp=datetime.now(timezone.utc), source="simulated",
                       rainfall=round(max(0, rain + noise), 2), temperature=round(27 + 2 * math.sin(t / 8 + phase), 2),
                       humidity=round(min(100, 47 + rain * 0.5), 2), soil_moisture=round(moisture, 2),
                       ground_vibration=round(vibration, 2), displacement=round(displacement, 2),
                       strain=round(strain, 2), pore_pressure=round(24 + moisture * 0.55, 2))

    def step(self) -> None:
        self.tick += 1
        for zone in ZONES:
            self.submit(self.reading(zone["id"]))

    async def _loop(self) -> None:
        while True:
            self.step()
            await asyncio.sleep(self.interval)

    def start(self) -> dict:
        if not self.running:
            self.task = asyncio.create_task(self._loop())
        return self.status()

    def stop(self) -> dict:
        if self.task:
            self.task.cancel()
            self.task = None
        return self.status()

    def set_scenario(self, scenario: str) -> dict:
        self.scenario = scenario
        self.tick = 0
        return self.status()
