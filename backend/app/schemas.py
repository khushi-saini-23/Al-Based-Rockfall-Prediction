from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class Reading(BaseModel):
    zone_id: str = Field(min_length=1, max_length=40)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: Literal["simulated", "physical"]
    rainfall: float = Field(ge=0, le=500)
    temperature: float = Field(ge=-50, le=80)
    humidity: float = Field(ge=0, le=100)
    soil_moisture: float = Field(ge=0, le=100)
    ground_vibration: float = Field(ge=0, le=100)
    displacement: float = Field(ge=0, le=100)
    strain: float = Field(ge=0, le=100)
    pore_pressure: float = Field(ge=0, le=1000)


class PredictionRequest(BaseModel):
    reading: Reading


class ScenarioRequest(BaseModel):
    scenario: Literal["normal", "heavy_rain", "slope_movement"]


class TestAlertRequest(BaseModel):
    zone_id: str = Field(default="north_wall", min_length=1, max_length=40)
    risk_level: Literal["MEDIUM", "HIGH", "CRITICAL"] = "HIGH"


class MLFeatureRequest(BaseModel):
    location_id: str = Field(min_length=1, max_length=40)
    input_timestamp: datetime
    data_provenance: Literal["real_observed"]
    features: dict[str, float | None]
