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
from app.schemas import MLFeatureRequest, PredictionRequest, Reading, ScenarioRequest, TestAlertRequest
from app.services.risk import assess
from app.services.recommendations import recommendation
from app.services.terrain import TerrainError, analyze_ascii_grid
from app.services.vision import VisionUnavailable, detect_image, status as vision_status
from app.services.demo_data import DemoDataError, as_demo_reading, demo_events, demo_locations, inspect_datasets, recent_aligned_rows
from app.simulator.sensor_simulator import Simulator, ZONES

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("geoguards")
store = Store()


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_alert(zone_id: str, level: str, *, test: bool = False, reasons: list[str] | None = None) -> dict:
    if not test:
        existing = store.list("alerts", limit=30, zone_id=zone_id)
        if any(a["risk_level"] == level and not a["acknowledged"] and not a["test"] for a in existing):
            return next(a for a in existing if a["risk_level"] == level and not a["acknowledged"] and not a["test"])
    alert = {
        "id": str(uuid4()), "zone_id": zone_id, "risk_level": level, "timestamp": utcnow(),
        "acknowledged": False, "test": test, "source": "simulated" if test else "system",
        "message": f"{level} demonstration risk in {zone_id.replace('_', ' ').title()}. Inspect zone and follow site procedures.",
        "reasons": reasons or [], "recommended_action": recommendation(level),
        "notification_status": "test_mode_no_delivery", "site_alarm": "simulated" if level in {"HIGH", "CRITICAL"} else "inactive",
    }
    return store.insert("alerts", alert)


def ingest(reading: Reading, metadata: dict | None = None) -> dict:
    record = store.insert("sensor_readings", {**reading.model_dump(mode="json"), **(metadata or {})})
    assessment = assess(reading)
    prediction = store.insert("predictions", {**assessment, "assessment_type": "DEMO_RULES",
        "input_timestamp": reading.timestamp.isoformat(), "recommended_action": recommendation(assessment["risk_level"]),
        **({
        "dataset_provenance": "synthetic_demo_only", "unit_alignment": "provisional_hourly_demo_mapping"}
        if metadata and metadata.get("dataset_provenance") == "synthetic_demo_only" else {})})
    # Historical CSV samples exercise assessments, but must not raise current alerts.
    if prediction["risk_level"] in {"MEDIUM", "HIGH"} and not (metadata and metadata.get("dataset_provenance") == "synthetic_demo_only"):
        create_alert(reading.zone_id, prediction["risk_level"], reasons=prediction["reasons"])
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


@app.get("/api/models/status")
def model_status():
    research = ml_status()
    return {"active_assessment": "DEMO_RULES", "validated_ml_available": False,
            "trained_model_installed": research["available"], "calibrated_probability_available": False,
            "reason": "Experimental research model available separately; rules remain the dashboard default."
                      if research["available"] else "No suitable real mine monitoring dataset with independently verified rockfall outcomes is installed."}


@app.get("/api/ml/status")
def ml_status():
    try:
        from ml.model_registry import status
        return status()
    except ImportError:
        return {"available": False, "active_assessment": "DEMO_RULES", "model_name": None,
                "validation_status": "unavailable", "reason": "Install backend/requirements-ml.txt for research ML"}


@app.get("/api/ml/comparison")
def ml_comparison():
    from ml.model_registry import comparison
    return comparison()


@app.get("/api/ml/assessments")
def ml_assessments(limit: int = Query(100, ge=1, le=500)):
    return store.list("ml_assessments", limit)


@app.post("/api/ml/predict")
def ml_predict(request: MLFeatureRequest):
    try:
        from ml.inference import infer
        result = infer(request.location_id, request.input_timestamp, request.features)
    except ImportError:
        return {"status": "model_unavailable", "prediction_source": "DEMO_RULES", "risk_level": "NO DATA",
                "risk_probability": None, "reason": "Install backend/requirements-ml.txt; rules remain at /api/predict"}
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(422, str(exc)) from exc
    if result["status"] == "experimental_assessment":
        store.insert("ml_assessments", {"id": str(uuid4()), "zone_id": request.location_id,
                                        "timestamp": result["assessment_timestamp"], **result})
    return result


@app.get("/api/zones")
def zones():
    csv_zones = [{"id": location_id, "name": f"Demo {location_id}",
                  "x": 12 + (index % 5) * 18, "y": 18 + (index // 5) * 57,
                  "geometry_source": "schematic_demo", "dem_available": False,
                  "data_provenance": "synthetic_demo_only"}
                 for index, location_id in enumerate(demo_locations())]
    return [{**z, "geometry_source": "schematic_demo", "dem_available": False} for z in ZONES] + csv_zones


@app.post("/api/sensors")
def post_sensor(reading: Reading):
    if reading.zone_id not in {z["id"] for z in zones()}:
        raise HTTPException(422, "Unknown zone_id")
    return ingest(reading)


@app.get("/api/sensors/latest")
def latest_sensors():
    return [rows[0] for z in zones() if (rows := store.list("sensor_readings", 1, z["id"]))]


@app.get("/api/sensors/history")
def sensor_history(zone_id: str | None = None, limit: int = Query(100, ge=1, le=500)):
    return store.list("sensor_readings", limit, zone_id)


@app.get("/api/sensors/status")
def sensor_status():
    now = datetime.now(timezone.utc)
    status = []
    for zone in zones():
        rows = store.list("sensor_readings", 1, zone["id"])
        if not rows:
            state = "no_readings"
            latest = None
        else:
            latest = rows[0]
            stamp = datetime.fromisoformat(latest["timestamp"].replace("Z", "+00:00"))
            if latest.get("dataset_provenance") == "synthetic_demo_only":
                state = "historical_demo"
            elif latest["source"] == "simulated":
                state = "simulator_recent" if (now - stamp).total_seconds() <= 15 else "simulator_stale"
            else:
                state = "reading_recent" if (now - stamp).total_seconds() <= 300 else "reading_stale"
        status.append({"zone_id": zone["id"], "status": state,
                       "last_reading_at": latest["timestamp"] if latest else None,
                       "source": latest["source"] if latest else None,
                       "connection_verified": False})
    return status


@app.post("/api/predict")
def predict(request: PredictionRequest):
    if request.reading.zone_id not in {z["id"] for z in zones()}:
        raise HTTPException(422, "Unknown zone_id")
    prediction = assess(request.reading)
    prediction.update({"assessment_type": "DEMO_RULES", "input_timestamp": request.reading.timestamp.isoformat(),
                       "recommended_action": recommendation(prediction["risk_level"])})
    store.insert("predictions", prediction)
    return prediction


@app.get("/api/predictions")
def predictions(zone_id: str | None = None, limit: int = Query(100, ge=1, le=500)):
    return store.list("predictions", limit, zone_id)


@app.get("/api/predictions/latest")
def latest_predictions():
    return [rows[0] for z in zones() if (rows := store.list("predictions", 1, z["id"]))]


@app.get("/api/demo/datasets")
def demo_datasets():
    try:
        return inspect_datasets()
    except DemoDataError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/demo/events")
def positive_demo_events():
    try:
        return {"events": demo_events(), "positive_only": True,
                "unlisted_times_are_unknown": True, "provenance": "synthetic_demo_only"}
    except DemoDataError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/demo/import")
def import_demo(limit_per_location: int = Query(30, ge=1, le=100)):
    """Import a bounded recent window for dashboard testing; never import event labels."""
    try:
        aligned = recent_aligned_rows(limit_per_location)
    except DemoDataError as exc:
        raise HTTPException(422, str(exc)) from exc
    imported = skipped = 0
    for row in aligned:
        reading = as_demo_reading(row)
        if store.has_demo_reading(row["location_id"], reading.model_dump(mode="json")["timestamp"]):
            skipped += 1
            continue
        ingest(reading, {"dataset_provenance": "synthetic_demo_only", "dataset_location_id": row["location_id"],
                         "unit_alignment": "provisional_hourly_demo_mapping", "raw_demo_features": row})
        imported += 1
    return {"imported": imported, "skipped_existing": skipped, "available_locations": len(demo_locations()),
            "event_labels_imported": 0, "provenance": "synthetic_demo_only",
            "assessment": "provisional rules only; CSV unit mapping assumes one-hour samples"}


@app.post("/api/detect")
async def detect(file: UploadFile = File(...), zone_id: str = "north_wall"):
    if zone_id not in {z["id"] for z in zones()}:
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
    try:
        inference = detect_image(data)
    except VisionUnavailable as exc:
        inference = {"status": "unavailable", "detections": [], "annotated_image": None,
                     "message": f"{exc}. No image analysis was performed."}
    result = {"id": str(uuid4()), "zone_id": zone_id, "timestamp": utcnow(), "filename": Path(file.filename or "image").name,
              **inference, "source": "uploaded_image"}
    return store.insert("detection_results", result)


@app.get("/api/detect/status")
def detection_status():
    return vision_status()


@app.get("/api/detections")
def detections(limit: int = Query(50, ge=1, le=500)):
    return store.list("detection_results", limit)


@app.post("/api/terrain/analyze")
async def terrain_analyze(file: UploadFile = File(...), zone_id: str | None = None):
    if zone_id and zone_id not in {z["id"] for z in zones()}:
        raise HTTPException(422, "Unknown zone_id")
    if Path(file.filename or "").suffix.lower() not in {".asc", ".txt"}:
        raise HTTPException(415, "Upload an ESRI ASCII DEM (.asc or .txt)")
    content = await file.read(10_000_001)
    if len(content) > 10_000_000:
        raise HTTPException(413, "DEM must be under 10 MB")
    try:
        analysis = analyze_ascii_grid(content)
    except TerrainError as exc:
        raise HTTPException(422, str(exc)) from exc
    return store.insert("terrain_analyses", {"id": str(uuid4()), "timestamp": utcnow(),
        "zone_id": zone_id, "filename": Path(file.filename or "grid.asc").name, **analysis,
        "zone_association": "user_selected_unverified" if zone_id else "none"})


@app.get("/api/terrain/analyses")
def terrain_analyses(limit: int = Query(30, ge=1, le=100)):
    return store.list("terrain_analyses", limit)


@app.get("/api/alerts")
def alerts(limit: int = Query(100, ge=1, le=500)):
    return store.list("alerts", limit)


@app.post("/api/alerts/test")
def test_alert(request: TestAlertRequest):
    if request.zone_id not in {z["id"] for z in zones()}:
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
    statuses = sensor_status()
    return {"overall_risk": max((p["risk_level"] for p in current), key=rank.get, default="NO DATA"),
            "total_zones": len(zones()),
            "reporting_zones": sum(item["status"] in {"simulator_recent", "reading_recent"} for item in statuses),
            "historical_demo_zones": sum(item["status"] == "historical_demo" for item in statuses),
            "active_alerts": len(active),
            "storage": "mongodb" if store.db is not None else "memory", "model_status": "provisional rules only",
            "simulation": simulator.status(), "prototype": True}
