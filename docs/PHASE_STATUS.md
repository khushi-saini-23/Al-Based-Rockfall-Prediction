# GeoGuards implementation status

## Phase 2 — functional monitoring and dashboard

The simulator and supplied synthetic CSVs feed the existing sensor and
provisional rule workflow. Sensor status distinguishes historical CSV samples,
recent/stale simulator readings, recent/stale externally posted readings, and
zones with no readings. This is **receipt status**, not proof of a physical
sensor connection. The dashboard displays zone assessments, factors, historical
trends, and rule-specific suggested actions. Alerts include factors and actions,
are deduplicated, can be acknowledged, and are dashboard-only. Importing 2023
CSV samples cannot create current alerts. No SMS, email or physical alarm is
delivered.

## Phase 3 — image and terrain interfaces

The terrain page accepts ESRI ASCII elevation grids (`.asc` or `.txt`, up to
10 MB), validates dimensions and cells, and computes elevation, Horn-method
slope, aspect and local elevation range. It stores descriptive analysis
summaries, not the raster. A selected zone is an **unverified user tag**; no
coordinate reference system or mine boundary has been supplied, so terrain
results are not geographically overlaid on the map or used as risk inputs.
GeoTIFF import and surveyed-zone overlay remain outstanding.

The image endpoint supports a pinned local YOLO11 nano general-object demo after
running `backend/scripts/setup_vision_demo.py` and installing
`backend/requirements-vision.txt`. The binary is downloaded separately and is
not committed. It returns actual class names, confidence and bounding boxes;
the UI draws the boxes and labels results `analyzed_demo_objects`. These are
ordinary object classes, not rockfall hazards. A user-configured geological
weight file takes precedence and returns `analyzed_unvalidated`. Without
weights or dependencies, analysis reports unavailable and creates no fabricated
detections. Neither mode predicts future rockfall or establishes mine-site
accuracy. Model classes, license, test domain and site evaluation need review.

## Phase 4 — real data acquisition review

Potential public sources and their suitability limits are in
[`REAL_DATA_REVIEW.md`](REAL_DATA_REVIEW.md). No genuine mine dataset was
silently substituted for the supplied synthetic data. `datasets/real/` remains
empty pending provenance and target review.

## Phase 5 — scientific ML

**Research software implemented; real-data training blocked.** Reusable
causal alignment, features, verified-event/coverage targets, chronological
splits, Random Forest and XGBoost training, evaluation, artifact persistence,
and optional TreeSHAP are in `backend/ml/`. See [ML_PIPELINE.md](ML_PIPELINE.md).
There is no dataset pairing genuine
mine sensor histories with independently verified rockfall events and observed
non-event periods. The three supplied event labels are synthetic and
rule-generated. Training on them would measure reproduction of the generating
rules, not rockfall prediction. Before training, define the event and forecast
horizon, reconcile units and zone/time references, establish observation
coverage, audit leakage, and hold out time periods, events and mines where
possible. Fit preprocessing on training folds only, compare against the
provisional baseline, and evaluate false alarms, missed events and calibration.

## Phase 6 — validated ML integration

**Research integration implemented; validated deployment blocked by data and
review.** `GET /api/models/status` reports `DEMO_RULES` and no validated model.
Separate `/api/ml/*` endpoints and a Research ML status panel are available,
but no model is active. The existing `assess(reading)` interface remains the fallback.
Do not label an artifact `VALIDATED_ML`, display event probabilities, or
activate operational alerts without a reviewed dataset, evaluation report,
versioned preprocessing/model artifact, calibrated horizon and site safety
approval. Add those behind `assess(reading)` while preserving the current API
fields once the evidence exists.
