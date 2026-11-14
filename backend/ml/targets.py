"""Future-event targets require independent events or verified quiet coverage."""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def read_labels(event_path: Path, coverage_path: Path, *, fixture: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not event_path.is_file() or not coverage_path.is_file():
        raise FileNotFoundError("Verified event and observation-coverage files are both required")
    events = pd.read_csv(event_path)
    coverage = pd.read_csv(coverage_path)
    expected_event = {"timestamp", "location_id", "event_id", "verification_status", "data_provenance"}
    expected_coverage = {"start_timestamp", "end_timestamp", "location_id", "coverage_status", "data_provenance"}
    if not expected_event.issubset(events) or not expected_coverage.issubset(coverage):
        raise ValueError("Event or coverage schema is incomplete")
    provenance = "unit_test_fixture" if fixture else "real_observed"
    if not events.data_provenance.eq(provenance).all() or not coverage.data_provenance.eq(provenance).all():
        raise ValueError("Event or coverage provenance is not approved")
    if not events.verification_status.eq("independently_verified").all():
        raise ValueError("Every training event must be independently verified")
    if not coverage.coverage_status.eq("verified_complete").all():
        raise ValueError("Negative periods require verified complete observation coverage")
    if events[["timestamp", "location_id", "event_id"]].isna().any().any() or coverage[["start_timestamp", "end_timestamp", "location_id"]].isna().any().any():
        raise ValueError("Missing event or coverage key")
    if events.event_id.duplicated().any():
        raise ValueError("Duplicate event_id")
    for frame, columns in ((events, ["timestamp"]), (coverage, ["start_timestamp", "end_timestamp"])):
        for column in columns:
            if not frame[column].astype(str).str.contains(r"(?:Z|[+-]\d\d:\d\d)$", regex=True).all():
                raise ValueError(f"{column} needs an explicit timezone")
            frame[column] = pd.to_datetime(frame[column], utc=True, errors="coerce")
            if frame[column].isna().any():
                raise ValueError(f"Invalid {column}")
    if (coverage.end_timestamp <= coverage.start_timestamp).any():
        raise ValueError("Coverage end must follow start")
    return events, coverage


def build_targets(features: pd.DataFrame, events: pd.DataFrame, coverage: pd.DataFrame, horizon_hours: int) -> pd.DataFrame:
    if horizon_hours < 1:
        raise ValueError("Prediction horizon must be positive")
    result = features.copy()
    labels = []
    event_by_zone = {zone: group.timestamp.sort_values() for zone, group in events.groupby("location_id")}
    coverage_by_zone = {zone: group for zone, group in coverage.groupby("location_id")}
    horizon = pd.Timedelta(hours=horizon_hours)
    for row in result.itertuples():
        end = row.timestamp + horizon
        zone_events = event_by_zone.get(row.location_id)
        positive = zone_events is not None and ((zone_events > row.timestamp) & (zone_events <= end)).any()
        if positive:
            labels.append(1)
            continue
        intervals = coverage_by_zone.get(row.location_id)
        observed = intervals is not None and ((intervals.start_timestamp <= row.timestamp) & (intervals.end_timestamp >= end)).any()
        labels.append(0 if observed else pd.NA)
    result["target"] = pd.array(labels, dtype="Int64")
    return result
