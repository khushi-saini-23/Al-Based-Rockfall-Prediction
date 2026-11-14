"""Read the supplied synthetic CSVs without creating a merged dataset or labels."""

from __future__ import annotations

import csv
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path

from app.schemas import Reading

DEMO_DIR = Path(__file__).resolve().parents[3] / "datasets" / "demo"
FILES = {
    "environmental": "01_environmental_data.csv",
    "vibration": "02_vibration_sensor_data.csv",
    "displacement_strain": "03_displacement_strain_data.csv",
    "geotechnical": "04_geotechnical_data.csv",
    "events": "05_rockfall_events.csv",
}
NUMERIC = {
    "environmental": ("rainfall_mm", "temperature_c", "humidity_percent", "wind_speed_m_s"),
    "vibration": ("vibration_mm_s",),
    "displacement_strain": ("displacement_mm_h", "strain_microstrain"),
    "geotechnical": ("slope_angle_deg", "elevation_m", "aspect_deg", "surface_roughness_index",
                     "terrain_ruggedness_index", "pore_pressure_kpa", "soil_moisture_percent",
                     "factor_of_safety_proxy"),
    "events": ("rockfall_event",),
}
PROVENANCE = "synthetic_demo_only"


class DemoDataError(ValueError):
    pass


def _rows(kind: str):
    path = DEMO_DIR / FILES[kind]
    if not path.is_file():
        raise DemoDataError(f"Required demo dataset is missing: {path}")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"timestamp", "location_id", "data_provenance", *NUMERIC[kind]}
        if kind == "events":
            required.add("event_label_source")
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise DemoDataError(f"{path.name}: missing columns {sorted(required - set(reader.fieldnames or []))}")
        for line, row in enumerate(reader, 2):
            if None in row or any(value is None or not value.strip() for value in row.values()):
                raise DemoDataError(f"{path.name}:{line}: missing or extra field")
            try:
                stamp = datetime.fromisoformat(row["timestamp"])
            except ValueError as exc:
                raise DemoDataError(f"{path.name}:{line}: invalid timestamp") from exc
            if stamp.tzinfo is None or stamp.utcoffset() != timezone.utc.utcoffset(stamp):
                raise DemoDataError(f"{path.name}:{line}: timestamp must have a UTC offset")
            if row["data_provenance"] != PROVENANCE:
                raise DemoDataError(f"{path.name}:{line}: unexpected provenance")
            try:
                for field in NUMERIC[kind]:
                    value = float(row[field])
                    if not (-float("inf") < value < float("inf")):
                        raise ValueError("non-finite number")
            except ValueError as exc:
                raise DemoDataError(f"{path.name}:{line}: invalid numeric field") from exc
            if kind == "events" and (row["rockfall_event"] != "1" or
                                     row["event_label_source"] != "synthetic_rule_based_demo_label"):
                raise DemoDataError(f"{path.name}:{line}: unexpected event label")
            yield row


def inspect_datasets() -> dict:
    reports = {}
    sensor_keys = {}
    for kind, filename in FILES.items():
        keys = set()
        locations = Counter()
        count = 0
        first = last = None
        for row in _rows(kind):
            key = (row["timestamp"], row["location_id"])
            if key in keys:
                raise DemoDataError(f"{filename}: duplicate timestamp/location_id {key}")
            keys.add(key)
            locations[row["location_id"]] += 1
            first = key[0] if first is None or key[0] < first else first
            last = key[0] if last is None or key[0] > last else last
            count += 1
        if kind != "events":
            sensor_keys[kind] = keys
        reports[kind] = {"file": filename, "rows": count, "locations": dict(sorted(locations.items())),
                         "first_timestamp": first, "last_timestamp": last, "missing_values": 0,
                         "duplicate_keys": 0, "columns": ["timestamp", "location_id", *NUMERIC[kind],
                                                              *( ["event_label_source"] if kind == "events" else []),
                                                              "data_provenance"]}
    baseline = sensor_keys["environmental"]
    for kind, keys in sensor_keys.items():
        if keys != baseline:
            raise DemoDataError(f"{FILES[kind]}: timestamp/location_id keys do not match environmental data")
    event_keys = {(row["timestamp"], row["location_id"]) for row in _rows("events")}
    if not event_keys.issubset(baseline):
        raise DemoDataError("Event timestamps/locations do not match sensor readings")
    return {"provenance": PROVENANCE, "event_labels": "synthetic_rule_based_demo_label",
            "events_are_positive_only": True, "unlisted_events_are_unknown": True,
            "sensor_keys_aligned": True, "datasets": reports}


def demo_locations() -> list[str]:
    if not (DEMO_DIR / FILES["environmental"]).is_file():
        return []
    return sorted({row["location_id"] for row in _rows("environmental")})


def demo_events() -> list[dict]:
    """Return supplied positive rows only; absence is never converted to zero."""
    return [{"timestamp": row["timestamp"], "location_id": row["location_id"],
             "rockfall_event": 1, "event_label_source": row["event_label_source"],
             "data_provenance": row["data_provenance"]} for row in _rows("events")]


def recent_aligned_rows(limit_per_location: int = 30) -> list[dict]:
    """Join a bounded recent window in memory by both keys; leave event labels separate."""
    if not 1 <= limit_per_location <= 100:
        raise DemoDataError("limit_per_location must be between 1 and 100")
    inspect_datasets()
    selected = {}
    for kind in ("environmental", "vibration", "displacement_strain", "geotechnical"):
        per_location = {}
        for row in _rows(kind):
            per_location.setdefault(row["location_id"], deque(maxlen=limit_per_location)).append(row)
        selected[kind] = {(row["timestamp"], row["location_id"]): row
                          for rows in per_location.values() for row in rows}
    keys = set(selected["environmental"])
    for kind, rows in selected.items():
        if set(rows) != keys:
            raise DemoDataError(f"Recent keys do not align in {FILES[kind]}")
    return [{"timestamp": timestamp, "location_id": location_id,
             **{field: float(value) for kind in selected for field, value in selected[kind][key].items()
                if field in NUMERIC[kind]}}
            for key in sorted(keys) for timestamp, location_id in (key,)]


def as_demo_reading(row: dict) -> Reading:
    """Adapt one hourly demo sample to the legacy Reading contract."""
    return Reading(zone_id=row["location_id"], timestamp=row["timestamp"], source="simulated",
                   rainfall=row["rainfall_mm"], temperature=row["temperature_c"],
                   humidity=row["humidity_percent"], soil_moisture=row["soil_moisture_percent"],
                   ground_vibration=row["vibration_mm_s"], displacement=row["displacement_mm_h"],
                   strain=row["strain_microstrain"], pore_pressure=row["pore_pressure_kpa"])
