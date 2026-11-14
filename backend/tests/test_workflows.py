from collections import defaultdict
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app, store


GRID = b"""ncols 3
nrows 3
xllcorner 0
yllcorner 0
cellsize 2
NODATA_value -9999
10 12 14
10 12 14
10 12 14
"""


def test_dem_analysis_and_status(monkeypatch):
    monkeypatch.setattr(store, "memory", defaultdict(list))
    monkeypatch.delenv("GEOLOGICAL_YOLO_WEIGHTS", raising=False)
    monkeypatch.setattr("app.services.vision.DEMO_WEIGHTS", Path("/nonexistent/geoguards-demo-weights.pt"))
    with TestClient(app) as client:
        response = client.post("/api/terrain/analyze", files={"file": ("test.asc", GRID, "text/plain")})
        assert response.status_code == 200
        result = response.json()
        assert result["slope_mean_deg"] == 45
        assert result["analyzed_cells"] == 1
        assert result["georeferenced_to_mine"] is False
        assert len(client.get("/api/terrain/analyses").json()) == 1
        assert client.post("/api/terrain/analyze", files={"file": ("bad.asc", b"bad", "text/plain")}).status_code == 422
        assert client.get("/api/sensors/status").json()[0]["status"] == "no_readings"
        assert client.get("/api/detect/status").json()["available"] is False
        assert client.get("/api/models/status").json()["validated_ml_available"] is False


def test_demo_alert_has_reasons_and_action(monkeypatch):
    monkeypatch.setattr(store, "memory", defaultdict(list))
    with TestClient(app) as client:
        reading = {"zone_id": "north_wall", "source": "simulated", "rainfall": 40,
                   "temperature": 25, "humidity": 75, "soil_moisture": 80,
                   "ground_vibration": 7, "displacement": 25, "strain": 60, "pore_pressure": 70}
        response = client.post("/api/sensors", json=reading)
        assert response.status_code == 200
        prediction = response.json()["prediction"]
        assert prediction["assessment_type"] == "DEMO_RULES"
        assert prediction["risk_probability"] is None
        assert prediction["recommended_action"]
        alert = client.get("/api/alerts").json()[0]
        assert alert["reasons"] == prediction["reasons"]
        assert alert["recommended_action"]
        assert alert["notification_status"] == "test_mode_no_delivery"
