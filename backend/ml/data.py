"""Read category files independently and align only past measurements."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import MLConfig

FILES = {
    "environmental": "environmental/readings.csv",
    "vibration": "vibration/readings.csv",
    "displacement_strain": "displacement_strain/readings.csv",
    "geotechnical": "geotechnical/readings.csv",
}
NUMERIC = {
    "environmental": ["rainfall_mm", "temperature_c", "humidity_percent"],
    "vibration": ["vibration_mm_s"],
    "displacement_strain": ["displacement_mm_h", "strain_microstrain"],
    "geotechnical": ["soil_moisture_percent", "pore_pressure_kpa", "slope_angle_deg", "elevation_m", "surface_roughness_index"],
}
OPTIONAL = {"environmental": ["wind_speed_m_s"], "geotechnical": ["terrain_ruggedness_index", "rock_density_kg_m3", "cohesion_kpa", "friction_angle_deg"]}
NONNEGATIVE = {"rainfall_mm", "vibration_mm_s", "displacement_mm_h", "strain_microstrain", "soil_moisture_percent",
               "pore_pressure_kpa", "slope_angle_deg", "surface_roughness_index", "terrain_ruggedness_index",
               "rock_density_kg_m3", "cohesion_kpa", "wind_speed_m_s"}


def read_category(path: Path, kind: str, *, fixture: bool = False) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"Missing {kind} data: {path}")
    if path.stat().st_size > 500_000_000:
        raise ValueError(f"{path}: file exceeds 500 MB; partition it before training")
    frame = pd.read_csv(path, dtype={"location_id": "string", "data_provenance": "string"})
    required = {"timestamp", "location_id", "data_provenance", *NUMERIC[kind]}
    absent = required - set(frame.columns)
    if absent:
        raise ValueError(f"{path.name}: missing columns {sorted(absent)}")
    provenance = {"unit_test_fixture"} if fixture else {"real_observed"}
    if not set(frame.data_provenance.dropna()) == provenance:
        raise ValueError(f"{path.name}: provenance must be {sorted(provenance)}")
    if frame[["timestamp", "location_id", "data_provenance"]].isna().any().any():
        raise ValueError(f"{path.name}: missing timestamp, location or provenance")
    stamps = pd.to_datetime(frame.timestamp, utc=True, errors="coerce")
    if stamps.isna().any() or not frame.timestamp.astype(str).str.contains(r"(?:Z|[+-]\d\d:\d\d)$", regex=True).all():
        raise ValueError(f"{path.name}: timestamps need explicit UTC offsets")
    frame["timestamp"] = stamps
    if frame.duplicated(["timestamp", "location_id"]).any():
        raise ValueError(f"{path.name}: duplicate timestamp/location_id")
    for column in NUMERIC[kind] + [name for name in OPTIONAL.get(kind, []) if name in frame]:
        original = frame[column]
        frame[column] = pd.to_numeric(original, errors="coerce")
        if (original.notna() & frame[column].isna()).any():
            raise ValueError(f"{path.name}: malformed numeric {column}")
        if frame[column].notna().any() and not frame[column].dropna().map(lambda x: float("-inf") < x < float("inf")).all():
            raise ValueError(f"{path.name}: non-finite {column}")
        if column in NONNEGATIVE and (frame[column].dropna() < 0).any():
            raise ValueError(f"{path.name}: negative {column}")
    for column in ("humidity_percent", "soil_moisture_percent"):
        if column in frame and (frame[column].dropna() > 100).any():
            raise ValueError(f"{path.name}: {column} exceeds 100%")
    if "slope_angle_deg" in frame and (frame.slope_angle_deg.dropna() > 90).any():
        raise ValueError(f"{path.name}: slope angle exceeds 90 degrees")
    frame = frame.sort_values(["location_id", "timestamp"]).reset_index(drop=True)
    if kind == "environmental":
        gaps = frame.groupby("location_id").timestamp.diff().dropna()
        if (gaps < pd.Timedelta(hours=1)).any():
            raise ValueError(f"{path.name}: rainfall intervals must be at least one hour apart")
    return frame


def quality_report(frame: pd.DataFrame) -> dict:
    numeric = frame.select_dtypes(include="number")
    # Flags investigate unusual magnitudes; no row is silently removed or relabelled.
    review_limits = {"rainfall_mm": 500, "vibration_mm_s": 500, "displacement_mm_h": 1000,
                     "strain_microstrain": 1_000_000, "pore_pressure_kpa": 100_000}
    return {"rows": len(frame), "missing_by_column": frame.isna().sum().astype(int).to_dict(),
            "duplicate_keys": int(frame.duplicated(["timestamp", "location_id"]).sum()),
            "magnitude_review_flags": {column: int((numeric[column].abs() > limit).sum())
                                       for column, limit in review_limits.items() if column in numeric}}


def align_measurements(config: MLConfig, *, fixture: bool = False) -> pd.DataFrame:
    sources = {kind: read_category(config.data_dir / filename, kind, fixture=fixture) for kind, filename in FILES.items()}
    # Environmental samples define prediction times. Every other stream is joined at or before that time.
    base = sources["environmental"].copy()
    tolerance = pd.Timedelta(hours=config.max_source_age_hours)
    for kind in ("vibration", "displacement_strain", "geotechnical"):
        right = sources[kind]
        chunks = []
        for location, left_zone in base.groupby("location_id", sort=False):
            right_zone = right[right.location_id == location].copy()
            right_zone = right_zone.drop(columns=["location_id", "data_provenance"])
            right_zone = right_zone.rename(columns={"timestamp": f"{kind}_observed_at"})
            joined = pd.merge_asof(left_zone.sort_values("timestamp"), right_zone.sort_values(f"{kind}_observed_at"),
                                   left_on="timestamp", right_on=f"{kind}_observed_at", direction="backward", tolerance=tolerance)
            chunks.append(joined)
        base = pd.concat(chunks, ignore_index=True)
    return base.sort_values(["location_id", "timestamp"]).reset_index(drop=True)
