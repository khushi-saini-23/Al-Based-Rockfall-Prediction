from __future__ import annotations

from collections import defaultdict
from threading import RLock
from typing import Any

from pymongo import MongoClient, DESCENDING

from .config import DATABASE_NAME, MONGODB_URL


class Store:
    collections = ("sensor_readings", "predictions", "alerts", "mine_zones", "detection_results", "simulation_sessions")

    def __init__(self, url: str | None = None) -> None:
        self.url = MONGODB_URL if url is None else url
        self.lock = RLock()
        self.memory: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.client = MongoClient(self.url, serverSelectionTimeoutMS=2500) if self.url else None
        self.db = self.client[DATABASE_NAME] if self.client is not None else None

    def connect(self) -> None:
        if self.client is not None:
            self.client.admin.command("ping")
            for name in self.collections:
                self.db[name].create_index("timestamp")

    def insert(self, collection: str, item: dict[str, Any]) -> dict[str, Any]:
        record = dict(item)
        if self.db is not None:
            self.db[collection].insert_one(record)
            record.pop("_id", None)
        else:
            with self.lock:
                self.memory[collection].append(record)
        return record

    def list(self, collection: str, limit: int = 100, zone_id: str | None = None) -> list[dict[str, Any]]:
        query = {"zone_id": zone_id} if zone_id else {}
        if self.db is not None:
            rows = list(self.db[collection].find(query, {"_id": 0}).sort("timestamp", DESCENDING).limit(limit))
        else:
            with self.lock:
                rows = [dict(x) for x in self.memory[collection] if not zone_id or x.get("zone_id") == zone_id]
            rows = sorted(rows, key=lambda x: x.get("timestamp", ""), reverse=True)[:limit]
        return rows

    def update(self, collection: str, item_id: str, changes: dict[str, Any]) -> bool:
        if self.db is not None:
            return self.db[collection].update_one({"id": item_id}, {"$set": changes}).matched_count > 0
        with self.lock:
            for item in self.memory[collection]:
                if item.get("id") == item_id:
                    item.update(changes)
                    return True
        return False
