from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
MODELS = PROJECT / "backend" / "models"


@dataclass(frozen=True)
class MLConfig:
    data_dir: Path = PROJECT / "datasets" / "real"
    horizon_hours: int = 6
    max_source_age_hours: int = 2
    rainfall_interval_hours: int = 1
    vibration_event_threshold_mm_s: float = 6.0
    seed: int = 42
    validation_fraction: float = 0.2
    test_fraction: float = 0.2
    decision_threshold: float | None = None
    decision_threshold_rationale: str | None = None
    feature_names: list[str] | None = None
    rf_candidates: list[dict] | None = None
    xgb_candidates: list[dict] | None = None
    model_version: str = "research-v1"
    reviewed_real_data: bool = False

    @classmethod
    def from_json(cls, path: Path) -> "MLConfig":
        values = json.loads(path.read_text())
        allowed = set(cls.__dataclass_fields__)
        unknown = set(values) - allowed
        if unknown:
            raise ValueError(f"Unknown ML settings: {sorted(unknown)}")
        if "data_dir" in values:
            values["data_dir"] = (path.parent / values["data_dir"]).resolve()
        config = cls(**values)
        if not 1 <= config.horizon_hours <= 168 or not 1 <= config.max_source_age_hours <= 24:
            raise ValueError("Invalid horizon or source age")
        if config.rainfall_interval_hours != 1:
            raise ValueError("This pipeline currently requires hourly interval rainfall")
        if not 0 < config.validation_fraction < 0.5 or not 0 < config.test_fraction < 0.5:
            raise ValueError("Invalid split fractions")
        if config.decision_threshold is not None and not 0 < config.decision_threshold < 1:
            raise ValueError("decision_threshold must be between 0 and 1")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", config.model_version):
            raise ValueError("model_version must be a short filename-safe identifier")
        if config.feature_names is not None and (not isinstance(config.feature_names, list) or not config.feature_names or
                                                  any(not isinstance(name, str) for name in config.feature_names) or
                                                  len(set(config.feature_names)) != len(config.feature_names)):
            raise ValueError("feature_names must be a nonempty list of unique names")
        for name in ("rf_candidates", "xgb_candidates"):
            candidates = getattr(config, name)
            if candidates is not None and (not isinstance(candidates, list) or not 1 <= len(candidates) <= 12 or
                                            any(not isinstance(item, dict) for item in candidates)):
                raise ValueError(f"{name} needs 1–12 parameter dictionaries")
        return config


def trusted_artifact_path(name: str) -> Path:
    if Path(name).name != name or not name.endswith(".joblib"):
        raise ValueError("Model artifact must be a local .joblib filename")
    path = (MODELS / name).resolve()
    if path.parent != MODELS.resolve():
        raise ValueError("Model artifact path is outside backend/models")
    return path
