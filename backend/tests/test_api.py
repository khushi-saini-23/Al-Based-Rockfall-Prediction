from fastapi.testclient import TestClient

from app.main import app, simulator, store


def test_simulator_ingestion_and_alerts():
    with TestClient(app) as client:
        assert client.get("/api/dashboard/summary").status_code == 200
        started = client.post("/api/simulator/start").json()
        assert started["running"] is True
        assert client.get("/api/simulator/status").json()["running"] is True
        assert client.post("/api/simulator/stop").json()["running"] is False
        assert client.post("/api/simulator/scenario", json={"scenario": "slope_movement"}).status_code == 200
        for _ in range(16):
            simulator.step()
        latest = client.get("/api/sensors/latest").json()
        assert len(latest) == 3
        assert all(item["source"] == "simulated" for item in latest)
        predictions = client.get("/api/predictions/latest").json()
        assert all(item["risk_level"] == "HIGH" for item in predictions)
        assert all(item["risk_probability"] is None for item in predictions)
        assert client.get("/api/alerts").json()


def test_validation_detection_and_test_alert():
    with TestClient(app) as client:
        assert client.post("/api/sensors", json={"zone_id": "north_wall"}).status_code == 422
        assert client.post("/api/detect", files={"file": ("x.txt", b"text", "text/plain")}).status_code == 415
        assert client.post("/api/detect", files={"file": ("bad.png", b"image", "image/png")}).status_code == 422
        result = client.post("/api/detect", files={"file": ("slope.png", b"\x89PNG\r\n\x1a\nplaceholder", "image/png")}).json()
        assert result["status"] == "unavailable" and result["detections"] == []
        alert = client.post("/api/alerts/test", json={"zone_id": "north_wall", "risk_level": "HIGH"}).json()
        assert alert["notification_status"] == "test_mode_no_delivery"
        assert client.patch(f"/api/alerts/{alert['id']}/acknowledge").json()["acknowledged"]
