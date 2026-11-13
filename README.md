# GeoGuards

An open-pit mine monitoring **software prototype**. Its built-in readings, zone geometry, risk rules, and alarm indicators are demonstrations, not validated safety forecasts or actual mine measurements. Do not use it for operational safety decisions.

## Run locally

Requirements: Python 3.11+, Node.js 20+. MongoDB is optional for local demonstration and required for durable history.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. API documentation is at http://localhost:8000/docs. Copy `.env.example` to `.env` to configure MongoDB or the frontend URL. With no `MONGODB_URL`, history is held in memory and is lost on restart. Start the simulator in the UI; it is off by default. The default scenario is `normal` and readings are sent through the same `/api/sensors` ingestion path used by future physical devices.

Run backend tests with `cd backend && pytest -q`. Run frontend checks with `cd frontend && npm run build`.

## What is implemented

- Warm, responsive React monitoring workspace with sidebar navigation for dashboard, map, alerts, risk analysis, sensors, image detection, reports and settings. The dashboard map uses USGS imagery tiles over Bingham Canyon Mine, with an arbitrary red demonstration polygon. It requires internet access. The separate Live Map page remains a fictional vector schematic.
- FastAPI ingestion, history, prediction, alert, simulator, detection and dashboard endpoints.
- Correlated, time-dependent readings for three fictional zones. Every simulated reading has `source: "simulated"`.
- Transparent provisional risk rules. `risk_probability` is `null` until a validated model is supplied. No claim of real-world accuracy is made.
- Optional MongoDB collections for readings, predictions, alerts, zones, detections and simulation sessions. If configured but unavailable, the API fails startup rather than silently losing durability.
- Image upload validation and a truthful unavailable state when geological YOLO weights are absent. No fabricated detections.
- Dashboard-only test alarms with deduplication and acknowledgement. No real SMS, email, siren or warning-light hardware is activated.
- A real mine basemap on the dashboard with an explicitly labeled red sample area that is unrelated to measured mine conditions or the simulated readings. The Live Map's vector zone polygons are fictional, not georeferenced, and contain no DEM.

## Next data and integration steps

To replace the baseline with ML, obtain a documented labeled rockfall dataset, assess label quality and leakage, split by mine/site and time where appropriate, evaluate against a baseline, then deploy a versioned model. To enable geological image detection, obtain appropriately licensed annotated images and train and validate task-specific YOLO weights. To build a real map, provide surveyed mine boundaries and DEM data. Real notifications and hardware require configured recipients, credentials, delivery testing and a safety review. None of those assets are included here.

## API overview

`POST /api/sensors`, `GET /api/sensors/latest`, `GET /api/sensors/history`, `POST /api/predict`, `GET /api/predictions`, `GET /api/predictions/latest`, `POST /api/detect`, `GET /api/detections`, `GET /api/alerts`, `POST /api/alerts/test`, `PATCH /api/alerts/{id}/acknowledge`, simulator start/stop/scenario/status, and dashboard summary/risk-distribution. All inputs and outputs are described in Swagger UI.

## Prototype limitations

The thresholds in `backend/app/services/risk.py` are invented for a UI demonstration and need qualified geotechnical review. Risk percentages are zone distributions, not event probabilities. The app has no authentication and must not be exposed to the public internet. The simulator uses fictional zones and coordinates. Notification delivery is intentionally disabled, even if credentials are set.
