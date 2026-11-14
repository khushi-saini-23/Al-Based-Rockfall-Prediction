"""Only load explicitly activated research artifacts from backend/models."""
from __future__ import annotations

import json
from functools import lru_cache

from .config import MODELS, trusted_artifact_path


def active_name() -> str | None:
    pointer = MODELS / "active.json"
    if not pointer.is_file():
        return None
    name = json.loads(pointer.read_text()).get("artifact")
    if not isinstance(name, str):
        raise ValueError("active.json needs an artifact filename")
    return name


@lru_cache(maxsize=2)
def _load(path: str, modified_ns: int):
    # joblib uses pickle. Never load a caller-supplied path or a file outside this directory.
    import joblib
    artifact = joblib.load(path)
    metadata = artifact.get("metadata", {})
    if metadata.get("prediction_source") != "EXPERIMENTAL_ML" or metadata.get("dataset_provenance") != "real_observed":
        raise ValueError("Active artifact is not an approved real-data research artifact")
    if not {"imputer", "model", "metadata"}.issubset(artifact):
        raise ValueError("Incomplete model artifact")
    return artifact


def load_active():
    name = active_name()
    if name is None:
        return None
    path = trusted_artifact_path(name)
    if not path.is_file():
        raise FileNotFoundError(f"Activated model is missing: {path.name}")
    return _load(str(path), path.stat().st_mtime_ns)


def status() -> dict:
    try:
        artifact = load_active()
    except (ValueError, FileNotFoundError, OSError) as exc:
        return {"available": False, "active_assessment": "DEMO_RULES", "model_name": None,
                "validation_status": "unavailable", "reason": str(exc)}
    if artifact is None:
        return {"available": False, "active_assessment": "DEMO_RULES", "model_name": None,
                "validation_status": "unavailable", "reason": "No reviewed real-data model has been activated"}
    info = artifact["metadata"]
    return {"available": True, "active_assessment": "EXPERIMENTAL_ML", "model_name": info["model_name"],
            "model_version": info["model_version"], "prediction_horizon_hours": info["horizon_hours"],
            "validation_status": info["validation_status"], "probabilities_calibrated": False,
            "rules_fallback_available": True}


def comparison() -> dict:
    path = MODELS / "comparison.json"
    if not path.is_file():
        return {"available": False, "reason": "No eligible real-data model comparison has been run"}
    report = json.loads(path.read_text())
    if report.get("status") != "research_unvalidated":
        return {"available": False, "reason": "Only fixture comparison results exist"}
    return {"available": True, **report}
