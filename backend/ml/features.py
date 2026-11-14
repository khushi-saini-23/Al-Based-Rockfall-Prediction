"""Causal, per-location features. Missing history remains missing."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import MLConfig

DIRECT = {
    "rainfall_mm": "rainfall_1h_mm",
    "temperature_c": "temperature_c",
    "humidity_percent": "humidity_percent",
    "soil_moisture_percent": "soil_moisture_percent",
    "pore_pressure_kpa": "pore_pressure_kpa",
    "slope_angle_deg": "slope_angle_deg",
    "strain_microstrain": "ground_strain_microstrain",
    "surface_roughness_index": "surface_roughness_index",
    "terrain_ruggedness_index": "terrain_ruggedness_index",
    "elevation_m": "elevation_m",
    "rock_density_kg_m3": "rock_density_kg_m3",
    "cohesion_kpa": "cohesion_kpa",
    "friction_angle_deg": "friction_angle_deg",
    "displacement_mm_h": "displacement_velocity_mm_h",
    "vibration_mm_s": "vibration_mm_s",
}


def make_features(aligned: pd.DataFrame, config: MLConfig) -> tuple[pd.DataFrame, list[str]]:
    frame = aligned.sort_values(["location_id", "timestamp"]).copy()
    feature_names = []
    for original, feature in DIRECT.items():
        if original in frame:
            frame[feature] = pd.to_numeric(frame[original], errors="coerce")
            feature_names.append(feature)
    engineered = ["rainfall_6h_mm", "rainfall_24h_mm", "displacement_acceleration_mm_h2",
                  "displacement_mean_6h_mm_h", "displacement_std_6h_mm_h",
                  "vibration_max_6h_mm_s", "vibration_events_6h"]
    feature_names.extend(engineered)
    for name in engineered:
        frame[name] = np.nan
    for _, zone in frame.groupby("location_id", sort=False):
        zone = zone.sort_values("timestamp")
        index = zone.index
        hourly = zone.timestamp.diff().eq(pd.Timedelta(hours=1)).to_numpy()
        consecutive = np.ones(len(zone), dtype=int)
        for i in range(1, len(zone)):
            consecutive[i] = consecutive[i - 1] + 1 if hourly[i] else 1
        rain = pd.Series(zone.rainfall_mm.to_numpy(), index=pd.DatetimeIndex(zone.timestamp))
        for hours in (6, 24):
            window = rain.rolling(f"{hours}h", closed="right")
            # Hourly rainfall intervals must cover the entire lookback; gaps are unknown.
            frame.loc[index, f"rainfall_{hours}h_mm"] = window.sum().where((window.count() == hours) & (consecutive >= hours)).to_numpy()
        velocity = pd.Series(zone.displacement_mm_h.to_numpy(), index=pd.DatetimeIndex(zone.timestamp))
        observed_movement = zone.displacement_strain_observed_at
        elapsed = observed_movement.diff().dt.total_seconds().div(3600).to_numpy()
        acceleration = np.divide(np.diff(velocity.to_numpy(), prepend=np.nan), elapsed,
                                 out=np.full(len(zone), np.nan), where=np.isfinite(elapsed) & (elapsed > 0))
        frame.loc[index, "displacement_acceleration_mm_h2"] = acceleration
        movement = velocity.rolling("6h", closed="right")
        frame.loc[index, "displacement_mean_6h_mm_h"] = movement.mean().where(movement.count() >= 2).to_numpy()
        frame.loc[index, "displacement_std_6h_mm_h"] = movement.std().where(movement.count() >= 2).to_numpy()
        vibration = pd.Series(zone.vibration_mm_s.to_numpy(), index=pd.DatetimeIndex(zone.timestamp))
        frame.loc[index, "vibration_max_6h_mm_s"] = vibration.rolling("6h", closed="right").max().to_numpy()
        fresh_vibration = zone.vibration_observed_at.ne(zone.vibration_observed_at.shift()).to_numpy()
        events = pd.Series((vibration.gt(config.vibration_event_threshold_mm_s).to_numpy() & fresh_vibration).astype(float), index=vibration.index)
        frame.loc[index, "vibration_events_6h"] = events.rolling("6h", closed="right").sum().to_numpy()
    frame["feature_missing_count"] = frame[feature_names].isna().sum(axis=1)
    return frame, feature_names
