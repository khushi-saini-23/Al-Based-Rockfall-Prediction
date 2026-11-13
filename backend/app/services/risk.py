from __future__ import annotations

from datetime import datetime, timezone

from app.schemas import Reading


def assess(reading: Reading) -> dict:
    """Provisional demonstration rules; no trained model or calibrated probability."""
    reasons = []
    if reading.rainfall >= 35:
        reasons.append("Heavy rainfall")
    if reading.soil_moisture >= 70:
        reasons.append("Elevated soil moisture")
    if reading.displacement >= 12:
        reasons.append("Increasing slope displacement")
    if reading.ground_vibration >= 6:
        reasons.append("Elevated vibration")
    if reading.strain >= 55:
        reasons.append("Elevated strain")
    if reading.pore_pressure >= 65:
        reasons.append("Elevated pore pressure")
    high = reading.displacement >= 20 or (reading.displacement >= 12 and reading.strain >= 55) or len(reasons) >= 3
    level = "HIGH" if high else "MEDIUM" if reasons else "LOW"
    return {"zone_id": reading.zone_id, "timestamp": datetime.now(timezone.utc).isoformat(),
            "risk_level": level, "risk_probability": None, "model_version": "provisional-rules-v1",
            "model_status": "No trained ML model installed", "source": reading.source,
            "reasons": reasons or ["No demonstration thresholds crossed"],
            "limitations": "Demonstration thresholds are unvalidated; no real-world safety forecast."}
