# Research ML pipeline: Random Forest and XGBoost

## Current status

The application still uses `DEMO_RULES` for dashboard risk assessments and
alerts. **No real-data ML model has been trained, activated, validated, or
selected. No scientific performance numbers exist.** The five supplied demo
CSVs are synthetic, and their three positive events are rule-generated. They
must not be used to train a purported rockfall predictor. The unit tests use
small, explicitly non-deployable fixtures only.

`VALIDATED_ML` is reserved for independently reviewed mine-site validation and
operational approval. A model produced by this pipeline is at most
`EXPERIMENTAL_ML`; activating it does not replace the dashboard rules or send
alerts. The API never returns an uncalibrated model score as an event
probability or maps it to a LOW/MEDIUM/HIGH/CRITICAL safety category.

## Required real data and provenance

Place original, approved files in these separate paths, without rewriting the
demo CSVs:

| Path under `datasets/real/` | Required numeric columns |
| --- | --- |
| `environmental/readings.csv` | `rainfall_mm`, `temperature_c`, `humidity_percent` |
| `vibration/readings.csv` | `vibration_mm_s` |
| `displacement_strain/readings.csv` | `displacement_mm_h`, `strain_microstrain` |
| `geotechnical/readings.csv` | `soil_moisture_percent`, `pore_pressure_kpa`, `slope_angle_deg`, `elevation_m`, `surface_roughness_index` |

Each measurement file must also have `timestamp`, `location_id`, and
`data_provenance=real_observed`. Timestamps need an explicit UTC offset and
must identify the observation time, not ingestion time. Units are encoded by
the column names; `rainfall_mm` must be an **hourly interval accumulation**.
Optional columns are `wind_speed_m_s`, `terrain_ruggedness_index`,
`rock_density_kg_m3`, `cohesion_kpa`, and `friction_angle_deg`. Optional
properties become features only if genuinely measured. The loader rejects
duplicate `(timestamp, location_id)` keys, malformed numeric values, invalid
percentages or slopes, and implausible negative measurements. Missing numeric
values remain missing and are reported. A magnitude review report flags very
large values without silently deleting them.

`rockfall_events/events.csv` requires `timestamp`, `location_id`, `event_id`,
`verification_status=independently_verified`, and
`data_provenance=real_observed`. `rockfall_events/coverage.csv` requires
`start_timestamp`, `end_timestamp`, `location_id`,
`coverage_status=verified_complete`, and `data_provenance=real_observed`.
Coverage means events would have been detected during that whole interval;
it is not a CSV with fabricated zeros. Document event definitions,
instrumentation, mine and zone coordinates, time zones, acquisition rights,
maintenance periods, and verification method before setting the review flag.

The current `datasets/real/` contains no measurements or verified outcomes.
The supplied demo schemas and limitations are in `datasets/demo/README.md`.

## Alignment, features and targets

Environmental observations define candidate assessment times. Each other
source is joined within the same `location_id` using the most recent reading
**at or before** that time, within `max_source_age_hours`. No future reading
can enter a historical feature. A missing or old measurement stays missing.
The current implementation handles differing source frequencies in this
causal join; it requires hourly environmental rainfall intervals for correct
1/6/24-hour accumulations. Six- and 24-hour rainfall features are missing
unless a complete consecutive hourly window exists. Displacement acceleration
uses elapsed time between distinct displacement observations, and vibration
event counts avoid counting the same reused observation twice.

Features include current rainfall, 6/24-hour rainfall, temperature, humidity,
soil moisture, pore pressure, slope angle, elevation, roughness, strain,
displacement velocity and acceleration, 6-hour movement mean/variability,
current and 6-hour maximum vibration, and 6-hour count above a configured
measurement threshold. Optional measured geotechnical columns are included
only when present. There is no invented rock type or DEM-derived feature.

The configurable target is an independently verified event in the same zone
within `(assessment_time, assessment_time + horizon]`; the default horizon is
six hours. A positive needs a verified event. A negative needs complete
verified observation coverage across the horizon with no event. All other
rows have an unknown target and are excluded. This target construction uses
future events as **labels only**, never as input features.

## Training and evaluation

`backend/ml/config.json` controls data path, horizon, source age, feature
threshold, random seed, split fractions, model candidates, version and decision
threshold. Real-data training requires `reviewed_real_data=true`, exactly
`datasets/real/`, and a documented, justified decision threshold. These flags
are gates, not proof that a dataset is scientifically adequate.

Both models use the same eligible rows, feature list, target and chronological
train/validation/test periods. A gap at least as long as the prediction
horizon is removed between periods. Imputation is fit on training data only.
At most two default hyperparameter candidates per model are evaluated on an
internal chronological training-period holdout; user-configured candidate
lists are limited to 12. Random Forest uses class weighting. XGBoost uses a
training-fold negative/positive ratio and early stopping on the internal
holdout when it contains both classes and enough rows. The final test period
is never used to tune parameters or choose a threshold.

Evaluation records precision, recall, F1, PR-AUC, ROC-AUC where defined,
confusion matrix, false positives/negatives, approximate false alarms per
monitored zone-day assuming hourly assessments, event detection recall and
median warning lead time where events are available. Brier score and
five-bin calibration diagnostics require at least 100 positive and 100
negative test rows. Undefined metrics are `null`, not zero or fabricated.
These are diagnostics; the pipeline does **not** fit a probability calibrator.
Global tree feature importance is stored. Individual TreeSHAP contributions
are optional if `shap` is installed and compatible; an unavailable explanation
is reported explicitly. Neither importance nor SHAP proves physical causation.

The comparison report intentionally does not declare a winner. A responsible
selection needs review of missed events, nuisance alarms, event independence,
unseen-zone or unseen-mine transfer, calibration, and site procedures.
Current code does not automatically perform a leave-one-mine-out evaluation.

## Commands

From the project root:

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements-ml.txt
# On macOS, XGBoost may also require: brew install libomp
.venv/bin/python -m pytest -q tests
.venv/bin/python -m ml.train --config ml/config.json
.venv/bin/python -m ml.train --config ml/config.json --model random_forest
.venv/bin/python -m ml.train --config ml/config.json --model xgboost
```

The last command **currently stops with a data-review error by design**. It
must not be bypassed to train on `datasets/demo/`. After acquiring and
reviewing suitable real data, populate the required paths, record provenance,
set `reviewed_real_data`, `decision_threshold`, and
`decision_threshold_rationale` in the config, and rerun. Successful research
training saves separate joblib artifacts and `comparison.json` under
`backend/models/`. Keep those artifacts private and load only trusted files.

Research models remain inactive until a reviewed local artifact is named in
`backend/models/active.json` as described in that folder's README. Status and
comparison are available at `GET /api/ml/status` and
`GET /api/ml/comparison`; `POST /api/ml/predict` takes a complete, current
engineered feature vector and returns an **unclassified research score** with
quality, model version, horizon and optional explanation. It stores research
assessments separately from rule predictions. `GET /api/ml/assessments` lists
that history. The inference request must declare `data_provenance=real_observed`;
the endpoint checks freshness and feature completeness but cannot by itself
authenticate a caller's measurement claims. When no model is active, it reports
unavailable and the existing `/api/predict` rules endpoint continues to work.

## Remaining gates

Acquire independently verified mine events and complete monitored non-event
periods; audit source units and observation coverage; assess missingness,
maintenance and outliers; verify unseen-event/site performance; choose and
justify a decision policy; evaluate and, if justified, calibrate probabilities;
obtain qualified geotechnical and mine safety review. Only then could a
separate deployment process consider `VALIDATED_ML` and operational alerts.
