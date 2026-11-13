from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.config import FRONTEND_URL, SIMULATION_ENABLED
from app.database import Store
from app.schemas import PredictionRequest, Reading, ScenarioRequest, TestAlertRequest
from app.services.risk import assess
from app.simulator.sensor_simulator import Simulator, ZONES

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("geoguards")
store = Store()


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_alert(zone_id: str, level: str, *, test: bool = False) -> dict:
    if not test:
        existing = store.list("alerts", limit=30, zone_id=zone_id)
        if any(a["risk_level"] == level and not a["acknowledged"] and not a["test"] for a in existing):
            return next(a for a in existing if a["risk_level"] == level and not a["acknowledged"] and not a["test"])
    alert = {
        "id": str(uuid4()), "zone_id": zone_id, "risk_level": level, "timestamp": utcnow(),
        "acknowledged": False, "test": test, "source": "simulated" if test else "system",
        "message": f"{level} demonstration risk in {zone_id.replace('_', ' ').title()}. Inspect zone and follow site procedures.",
        "notification_status": "test_mode_no_delivery", "site_alarm": "simulated" if level in {"HIGH", "CRITICAL"} else "inactive",
    }
    return store.insert("alerts", alert)


def ingest(reading: Reading) -> dict:
    record = store.insert("sensor_readings", reading.model_dump(mode="json"))
    prediction = store.insert("predictions", assess(reading))
    if prediction["risk_level"] in {"MEDIUM", "HIGH"}:
        create_alert(reading.zone_id, prediction["risk_level"])
    return {"reading": record, "prediction": prediction}


simulator = Simulator(ingest)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    store.connect()
    logger.info("GeoGuards store: %s", "MongoDB" if store.db is not None else "volatile in-memory")
    yield
    simulator.stop()
    if store.client is not None:
        store.client.close()


app = FastAPI(title="GeoGuards API", version="0.1.0", lifespan=lifespan,
              description="Software demonstration only. Simulated readings and provisional risk rules are not safety forecasts.")
app.add_middleware(CORSMiddleware, allow_origins=[FRONTEND_URL], allow_credentials=True,
                   allow_methods=["GET", "POST", "PATCH"], allow_headers=["*"])


@app.get("/api/health")
def health():
    return {"status": "ok", "storage": "mongodb" if store.db is not None else "memory", "prototype": True}


@app.get("/api/zones")
def zones():
    return [{**z, "geometry_source": "schematic_demo", "dem_available": False} for z in ZONES]


@app.post("/api/sensors")
def post_sensor(reading: Reading):
    if reading.zone_id not in {z["id"] for z in ZONES}:
        raise HTTPException(422, "Unknown zone_id")
    return ingest(reading)


@app.get("/api/sensors/latest")
def latest_sensors():
    return [rows[0] for z in ZONES if (rows := store.list("sensor_readings", 1, z["id"]))]


@app.get("/api/sensors/history")
def sensor_history(zone_id: str | None = None, limit: int = Query(100, ge=1, le=500)):
    return store.list("sensor_readings", limit, zone_id)


@app.post("/api/predict")
def predict(request: PredictionRequest):
    if request.reading.zone_id not in {z["id"] for z in ZONES}:
        raise HTTPException(422, "Unknown zone_id")
    prediction = assess(request.reading)
    store.insert("predictions", prediction)
    return prediction


@app.get("/api/predictions")
def predictions(zone_id: str | None = None, limit: int = Query(100, ge=1, le=500)):
    return store.list("predictions", limit, zone_id)


@app.get("/api/predictions/latest")
def latest_predictions():
    return [rows[0] for z in ZONES if (rows := store.list("predictions", 1, z["id"]))]


@app.post("/api/detect")
async def detect(file: UploadFile = File(...), zone_id: str = "north_wall"):
    if zone_id not in {z["id"] for z in ZONES}:
        raise HTTPException(422, "Unknown zone_id")
    if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(415, "Upload a JPEG, PNG or WebP image")
    data = await file.read(5_000_001)
    if len(data) > 5_000_000:
        raise HTTPException(413, "Image must be under 5 MB")
    if not data:
        raise HTTPException(422, "Image is empty")
    valid = ((file.content_type == "image/png" and data.startswith(b"\x89PNG\r\n\x1a\n")) or
             (file.content_type == "image/jpeg" and data.startswith(b"\xff\xd8\xff")) or
             (file.content_type == "image/webp" and data.startswith(b"RIFF") and data[8:12] == b"WEBP"))
    if not valid:
        raise HTTPException(422, "File content does not match its image type")
    result = {"id": str(uuid4()), "zone_id": zone_id, "timestamp": utcnow(), "filename": Path(file.filename or "image").name,
              "status": "unavailable", "detections": [], "annotated_image": None,
              "message": "Geological YOLO weights are not installed. No image analysis was performed.",
              "source": "uploaded_image"}
    return store.insert("detection_results", result)


@app.get("/api/detections")
def detections(limit: int = Query(50, ge=1, le=500)):
    return store.list("detection_results", limit)


@app.get("/api/alerts")
def alerts(limit: int = Query(100, ge=1, le=500)):
    return store.list("alerts", limit)


@app.post("/api/alerts/test")
def test_alert(request: TestAlertRequest):
    if request.zone_id not in {z["id"] for z in ZONES}:
        raise HTTPException(422, "Unknown zone_id")
    return create_alert(request.zone_id, request.risk_level, test=True)


@app.patch("/api/alerts/{alert_id}/acknowledge")
def acknowledge(alert_id: str):
    if not store.update("alerts", alert_id, {"acknowledged": True, "acknowledged_at": utcnow()}):
        raise HTTPException(404, "Alert not found")
    return {"id": alert_id, "acknowledged": True}


@app.post("/api/simulator/start")
async def simulator_start():
    if not SIMULATION_ENABLED:
        raise HTTPException(403, "Simulation is disabled")
    result = simulator.start()
    store.insert("simulation_sessions", {"id": str(uuid4()), "timestamp": utcnow(), "action": "start", **result})
    return result


@app.post("/api/simulator/stop")
async def simulator_stop():
    result = simulator.stop()
    store.insert("simulation_sessions", {"id": str(uuid4()), "timestamp": utcnow(), "action": "stop", **result})
    return result


@app.post("/api/simulator/scenario")
def simulator_scenario(request: ScenarioRequest):
    result = simulator.set_scenario(request.scenario)
    store.insert("simulation_sessions", {"id": str(uuid4()), "timestamp": utcnow(), "action": "scenario", **result})
    return result


@app.get("/api/simulator/status")
def simulator_status():
    return {**simulator.status(), "enabled": SIMULATION_ENABLED}


@app.get("/api/dashboard/risk-distribution")
def risk_distribution():
    current = latest_predictions()
    return {level: sum(p["risk_level"] == level for p in current) for level in ("LOW", "MEDIUM", "HIGH")}


@app.get("/api/dashboard/summary")
def dashboard_summary():
    current = latest_predictions()
    active = [a for a in store.list("alerts", 500) if not a["acknowledged"]]
    rank = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    return {"overall_risk": max((p["risk_level"] for p in current), key=rank.get, default="NO DATA"),
            "total_zones": len(ZONES), "reporting_zones": len(latest_sensors()), "active_alerts": len(active),
            "storage": "mongodb" if store.db is not None else "memory", "model_status": "provisional rules only",
            "simulation": simulator.status(), "prototype": True}
