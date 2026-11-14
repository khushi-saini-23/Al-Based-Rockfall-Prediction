"""Experimental feature-vector inference; never promotes an uncalibrated score to risk probability."""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pandas as pd

from .explainability import explain_individual
from .model_registry import load_active

RANGES = {"rainfall_1h_mm": (0, 500), "rainfall_6h_mm": (0, 3000), "rainfall_24h_mm": (0, 12000),
          "temperature_c": (-80, 80), "humidity_percent": (0, 100), "soil_moisture_percent": (0, 100),
          "slope_angle_deg": (0, 90), "vibration_mm_s": (0, 500), "pore_pressure_kpa": (0, 100_000)}


def infer(location_id: str, input_timestamp: datetime, features: dict[str, float], *,
          max_age_hours: int = 2) -> dict:
    now = datetime.now(timezone.utc)
    if input_timestamp.tzinfo is None:
        raise ValueError("input_timestamp must include a timezone")
    observed = input_timestamp.astimezone(timezone.utc)
    if observed > now + timedelta(minutes=5):
        raise ValueError("input_timestamp is in the future")
    if now - observed > timedelta(hours=max_age_hours):
        return {"status": "data_quality_blocked", "data_quality": "STALE_INPUT", "risk_level": "NO DATA",
                "prediction_source": None, "risk_probability": None, "reason": "Input is too old for current assessment"}
    artifact = load_active()
    if artifact is None:
        return {"status": "model_unavailable", "data_quality": "UNKNOWN", "risk_level": "NO DATA",
                "prediction_source": "DEMO_RULES", "risk_probability": None,
                "reason": "No research model is active; use the existing /api/predict rules endpoint"}
    metadata = artifact["metadata"]
    names = metadata["feature_names"]
    missing = [name for name in names if name not in features or features[name] is None]
    if missing:
        return {"status": "data_quality_blocked", "data_quality": "MISSING_FEATURES", "missing_features": missing,
                "risk_level": "NO DATA", "prediction_source": None, "risk_probability": None}
    if any(not isinstance(features[name], (int, float)) or not math.isfinite(float(features[name])) for name in names):
        raise ValueError("Features must be finite numeric values")
    out_of_range = [name for name in names if name in RANGES and not RANGES[name][0] <= features[name] <= RANGES[name][1]]
    if out_of_range:
        return {"status": "data_quality_blocked", "data_quality": "OUT_OF_RANGE", "out_of_range_features": out_of_range,
                "risk_level": "NO DATA", "prediction_source": None, "risk_probability": None}
    row = pd.DataFrame([{name: float(features[name]) for name in names}], columns=names)
    transformed = artifact["imputer"].transform(row)
    score = float(artifact["model"].predict_proba(transformed)[0, 1])
    explanation = explain_individual(artifact["model"], transformed, names)
    return {"status": "experimental_assessment", "location_id": location_id,
            "assessment_timestamp": now.isoformat(), "input_timestamp": observed.isoformat(),
            "prediction_source": "EXPERIMENTAL_ML", "model_name": metadata["model_name"],
            "model_version": metadata["model_version"], "prediction_horizon_hours": metadata["horizon_hours"],
            "validation_status": metadata["validation_status"], "data_quality": "OK",
            "risk_level": "UNCLASSIFIED", "risk_probability": None,
            "uncalibrated_model_score": score, "score_is_event_probability": False,
            "decision_above_research_threshold": score >= metadata["decision_threshold"],
            "global_feature_importance": metadata["global_feature_importance"][:5], **explanation,
            "limitations": "Research output only; no operational safety alert or calibrated event probability."}
