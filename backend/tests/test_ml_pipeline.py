from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import joblib
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import app
from ml.config import MLConfig
from ml.data import align_measurements, read_category
from ml.evaluate import chronological_split, score
from ml.features import make_features
from ml.inference import infer
from ml.targets import build_targets, read_labels
from ml.train import prepare, train_models


@pytest.fixture
def fixture_data(tmp_path):
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    files = {kind: [] for kind in ("environmental", "vibration", "displacement_strain", "geotechnical")}
    for zone in ("LOC_A", "LOC_B"):
        for hour in range(180):
            common = {"timestamp": (start + timedelta(hours=hour)).isoformat(), "location_id": zone,
                      "data_provenance": "unit_test_fixture"}
            files["environmental"].append({**common, "rainfall_mm": float(hour % 5), "temperature_c": 25,
                                           "humidity_percent": 60})
            files["vibration"].append({**common, "vibration_mm_s": float(hour % 7)})
            files["displacement_strain"].append({**common, "displacement_mm_h": float(hour) / 10,
                                                 "strain_microstrain": float(hour % 9)})
            files["geotechnical"].append({**common, "soil_moisture_percent": 50, "pore_pressure_kpa": 30,
                                           "slope_angle_deg": 35, "elevation_m": 500,
                                           "surface_roughness_index": 0.4})
    for kind, rows in files.items():
        directory = tmp_path / kind
        directory.mkdir()
        pd.DataFrame(rows).to_csv(directory / "readings.csv", index=False)
    event_dir = tmp_path / "rockfall_events"
    event_dir.mkdir()
    events = []
    for zone, hours in (("LOC_A", [25, 65, 95, 130, 165]), ("LOC_B", [40, 80, 120, 150, 175])):
        for hour in hours:
            events.append({"timestamp": (start + timedelta(hours=hour)).isoformat(), "location_id": zone,
                           "event_id": f"{zone}-{hour}", "verification_status": "independently_verified",
                           "data_provenance": "unit_test_fixture"})
    pd.DataFrame(events).to_csv(event_dir / "events.csv", index=False)
    pd.DataFrame([{"start_timestamp": start.isoformat(), "end_timestamp": (start + timedelta(hours=190)).isoformat(),
                   "location_id": zone, "coverage_status": "verified_complete", "data_provenance": "unit_test_fixture"}
                  for zone in ("LOC_A", "LOC_B")]).to_csv(event_dir / "coverage.csv", index=False)
    return MLConfig(data_dir=tmp_path, horizon_hours=1, decision_threshold=0.5)


def test_demo_data_cannot_train():
    with pytest.raises(ValueError, match="reviewed_real_data"):
        prepare(MLConfig(data_dir=Path(__file__).resolve().parents[2] / "datasets" / "demo"))


def test_alignment_is_causal_and_detects_bad_keys(fixture_data):
    path = fixture_data.data_dir / "vibration" / "readings.csv"
    frame = pd.read_csv(path)
    frame.loc[frame.location_id.eq("LOC_A") & frame.timestamp.eq("2025-01-01T01:00:00+00:00"), "timestamp"] = "2025-01-01T01:30:00+00:00"
    frame.to_csv(path, index=False)
    aligned = align_measurements(fixture_data, fixture=True)
    early = aligned[(aligned.location_id == "LOC_A") & (aligned.timestamp == pd.Timestamp("2025-01-01T01:00:00Z"))].iloc[0]
    assert early.vibration_observed_at == pd.Timestamp("2025-01-01T00:00:00Z")
    assert early.vibration_mm_s == 0
    frame = pd.read_csv(path)
    pd.concat([frame, frame.iloc[:1]]).to_csv(path, index=False)
    with pytest.raises(ValueError, match="duplicate"):
        read_category(path, "vibration", fixture=True)


def test_missing_values_and_causal_rolling(fixture_data):
    path = fixture_data.data_dir / "environmental" / "readings.csv"
    frame = pd.read_csv(path)
    frame.loc[(frame.location_id == "LOC_A") & frame.timestamp.str.contains("T02:00:00"), "rainfall_mm"] = None
    frame.to_csv(path, index=False)
    aligned = align_measurements(fixture_data, fixture=True)
    features, names = make_features(aligned, fixture_data)
    a = features[features.location_id == "LOC_A"].reset_index(drop=True)
    assert "rainfall_6h_mm" in names
    assert pd.isna(a.loc[5, "rainfall_6h_mm"])
    assert a.loc[6, "rainfall_1h_mm"] == 1
    assert a.loc[6, "displacement_acceleration_mm_h2"] == pytest.approx(0.1)
    assert a.loc[6, "vibration_max_6h_mm_s"] == 6
    # Changing a later sample cannot change an earlier feature.
    frame.loc[(frame.location_id == "LOC_A") & frame.timestamp.str.contains("T10:00:00"), "rainfall_mm"] = 500
    frame.to_csv(path, index=False)
    changed, _ = make_features(align_measurements(fixture_data, fixture=True), fixture_data)
    assert changed[changed.location_id == "LOC_A"].iloc[8].rainfall_6h_mm == a.loc[8, "rainfall_6h_mm"]


def test_targets_require_coverage_and_independent_events(fixture_data):
    aligned = align_measurements(fixture_data, fixture=True)
    features, _ = make_features(aligned, fixture_data)
    events, coverage = read_labels(fixture_data.data_dir / "rockfall_events/events.csv",
                                   fixture_data.data_dir / "rockfall_events/coverage.csv", fixture=True)
    coverage.loc[coverage.location_id == "LOC_A", "end_timestamp"] = pd.Timestamp("2025-01-01T20:00:00Z")
    labelled = build_targets(features, events, coverage, 1)
    a = labelled[ labelled.location_id == "LOC_A"].reset_index(drop=True)
    assert a.loc[24, "target"] == 1
    assert a.loc[10, "target"] == 0
    assert pd.isna(a.loc[30, "target"])
    event_file = fixture_data.data_dir / "rockfall_events/events.csv"
    invalid = pd.read_csv(event_file)
    invalid.loc[0, "verification_status"] = "unverified"
    invalid.to_csv(event_file, index=False)
    with pytest.raises(ValueError, match="independently verified"):
        read_labels(event_file, fixture_data.data_dir / "rockfall_events/coverage.csv", fixture=True)


def test_split_purges_horizon(fixture_data):
    labelled, _, _ = prepare(fixture_data, fixture=True)
    train, validation, test = chronological_split(labelled, 6)
    assert train.timestamp.max() + pd.Timedelta(hours=6) < validation.timestamp.min()
    assert validation.timestamp.max() + pd.Timedelta(hours=6) < test.timestamp.min()
    assert score([0, 0], [0.1, 0.2], 0.5)["pr_auc"] is None


def test_both_models_serialize_without_deployment(fixture_data, tmp_path, monkeypatch):
    import ml.inference as inference

    output = tmp_path / "artifacts"
    report = train_models(fixture_data, fixture=True, output_dir=output)
    assert set(report["models"]) == {"random_forest", "xgboost"}
    assert report["status"] == "software_test_only"
    for name in report["models"]:
        artifact = joblib.load(output / f"{name}-research-v1.joblib")
        assert artifact["metadata"]["prediction_source"] == "NON_DEPLOYABLE_TEST_FIXTURE"
        assert artifact["metadata"]["probabilities_calibrated"] is False
        assert len(artifact["metadata"]["feature_names"]) > 10
    research_fixture = joblib.load(output / "random_forest-research-v1.joblib")
    monkeypatch.setattr(inference, "load_active", lambda: research_fixture)
    missing = inference.infer("LOC_A", datetime.now(timezone.utc), {})
    assert missing["data_quality"] == "MISSING_FEATURES" and missing["risk_level"] == "NO DATA"
    values = {name: 1.0 for name in research_fixture["metadata"]["feature_names"]}
    bad_values = {**values, "rainfall_1h_mm": -1.0}
    assert inference.infer("LOC_A", datetime.now(timezone.utc), bad_values)["data_quality"] == "OUT_OF_RANGE"
    result = inference.infer("LOC_A", datetime.now(timezone.utc), values)
    assert result["prediction_source"] == "EXPERIMENTAL_ML"
    assert result["model_version"] == "research-v1" and result["risk_probability"] is None
    assert result["risk_level"] == "UNCLASSIFIED" and result["score_is_event_probability"] is False


def test_inference_quality_and_api_fallback(monkeypatch):
    import ml.model_registry as registry

    monkeypatch.setattr(registry, "active_name", lambda: None)
    stale = infer("LOC_A", datetime.now(timezone.utc) - timedelta(days=1), {})
    assert stale["data_quality"] == "STALE_INPUT" and stale["risk_level"] == "NO DATA"
    unavailable = infer("LOC_A", datetime.now(timezone.utc), {})
    assert unavailable["status"] == "model_unavailable"
    with TestClient(app) as client:
        assert client.get("/api/ml/status").json()["available"] is False
        assert client.get("/api/ml/comparison").json()["available"] is False
        assert client.get("/api/models/status").json()["active_assessment"] == "DEMO_RULES"
        response = client.post("/api/ml/predict", json={"location_id": "LOC_A",
            "input_timestamp": datetime.now(timezone.utc).isoformat(),
            "data_provenance": "real_observed", "features": {}})
        assert response.status_code == 200 and response.json()["status"] == "model_unavailable"
        assert client.get("/api/ml/assessments").json() == []
