from pathlib import Path
from collections import defaultdict

import pytest
from fastapi.testclient import TestClient

from app.main import app, store
from app.services import demo_data


def test_supplied_csvs_align_and_keep_positive_events_separate():
    report = demo_data.inspect_datasets()
    assert report["sensor_keys_aligned"] is True
    assert report["events_are_positive_only"] is True
    assert report["unlisted_events_are_unknown"] is True
    assert all(report["datasets"][kind]["rows"] == 5000 for kind in
               ("environmental", "vibration", "displacement_strain", "geotechnical"))
    assert report["datasets"]["events"]["rows"] == 3
    aligned = demo_data.recent_aligned_rows(2)
    assert len(aligned) == 20
    assert len({(row["timestamp"], row["location_id"]) for row in aligned}) == 20
    assert all("rockfall_event" not in row and "event_label_source" not in row for row in aligned)
    events = demo_data.demo_events()
    assert len(events) == 3
    assert all(row["rockfall_event"] == 1 and row["event_label_source"] == "synthetic_rule_based_demo_label"
               for row in events)


def test_missing_csv_is_reported(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(demo_data, "DEMO_DIR", tmp_path)
    with pytest.raises(demo_data.DemoDataError, match="missing"):
        demo_data.inspect_datasets()


def test_demo_import_is_idempotent_and_uses_provisional_rules(monkeypatch):
    monkeypatch.setattr(store, "memory", defaultdict(list))
    with TestClient(app) as client:
        response = client.post("/api/demo/import?limit_per_location=2")
        assert response.status_code == 200
        result = response.json()
        assert result["imported"] == 20
        assert result["event_labels_imported"] == 0
        assert client.get("/api/demo/events").json()["unlisted_times_are_unknown"] is True
        assert client.post("/api/demo/import?limit_per_location=2").json()["imported"] == 0
        summary = client.get("/api/dashboard/summary").json()
        assert summary["reporting_zones"] == 0
        assert summary["historical_demo_zones"] == 10
        latest = client.get("/api/sensors/latest").json()
        csv_readings = [row for row in latest if row["zone_id"].startswith("LOC_")]
        assert len(csv_readings) == 10
        assert all(row["source"] == "simulated" and
                   row["dataset_provenance"] == "synthetic_demo_only" for row in csv_readings)
        predictions = client.get("/api/predictions/latest").json()
        csv_predictions = [row for row in predictions if row["zone_id"].startswith("LOC_")]
        assert len(csv_predictions) == 10
        assert all(row["model_version"] == "provisional-rules-v1" and
                   row["risk_probability"] is None for row in csv_predictions)
        assert client.get("/api/alerts").json() == []
        test_alert = client.post("/api/alerts/test", json={"zone_id": "LOC_01", "risk_level": "HIGH"})
        assert test_alert.status_code == 200
        assert test_alert.json()["test"] is True
        assert not any("rockfall_event" in row for row in store.list("sensor_readings", 500))
